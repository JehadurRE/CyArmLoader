from datetime import datetime, timedelta
from flask.helpers import make_response
from core import app, mail, socketio
from flask import render_template, send_file, request, session, flash, url_for, redirect, Response, current_app
from pytube import YouTube, Playlist
import pytube.exceptions as exceptions
from io import BytesIO
from decouple import config
import os
from core.utils import playlist
from core import ig, yt
import shutil
from werkzeug.exceptions import NotFound, InternalServerError, MethodNotAllowed
from core.utils.blogs import fetch_posts, get_blog_post
from flask_mail import Message
from core.utils.contributors import get_contributors
from flask_socketio import send
from threading import Thread
from time import sleep

IG_USERNAME = config('IG_USERNAME', default='username')
IG_PASSWORD = config('IG_PASSWORD', default='password')
ADMIN_EMAIL = config('ADMIN_EMAIL', default=None)

file_data = {}
status = {}


@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            message = request.form.get('message')

            msg = Message("EazyLoader Notification",
                          sender=("EazyLoader", ADMIN_EMAIL), recipients=[ADMIN_EMAIL])
            msg.html = render_template('email_template.html', name=name, email=email,
                                       message=message, ip_addr=str(request.remote_addr))
            mail.send(msg)
            flash("We've received your details, thank you!", "success")
            return redirect(url_for('index', _anchor="contact"))

        except Exception as e:
            print(e)
            flash('Something went wrong! Try Again.', "error")
            return redirect(url_for('index', _anchor="contact"))
        
    return render_template('index.html', title='Home')


@app.route('/yt-downloader/video', methods=['GET', 'POST'])
def yt_video_downloader():
    if request.method == 'POST':
        session['video_link'] = request.form.get('video-url')
        try:
            highest_res = False
            url = YouTube(session['video_link'])
            url.check_availability()
            if url.streams.filter(res="1080p"):
                highest_res = url.streams.filter(res="1080p").first()
            return render_template('youtube/single/download.html', url=url, highest_res=highest_res)
        except exceptions.MembersOnly:
            flash('Join this channel to get access to members-only content like this video, and other exclusive perks.',
                  'error')
            return redirect(url_for('yt_video_downloader'))
        except exceptions.RecordingUnavailable:
            flash('The video recording is not available!', 'error')
            return redirect(url_for('yt_video_downloader'))
        except exceptions.VideoPrivate:
            flash(
                'This is a private video. Please sign in to verify that you may see it.')
            return redirect(url_for('yt_video_downloader'))
        except Exception as e:
            print(e)
            flash('Unable to fetch the video from YouTube', 'error')
            return redirect(url_for('yt_video_downloader'))

    return render_template('youtube/single/video.html', title='Download Video')



def start_preparation(msg, url, itag):
    
    buffer, filename = yt.download_single_video(url, itag)
    file_data.update(bfr=buffer)
    file_data.update(fname=filename)
    file_data.update(status="Done")
    status.update({f"{msg}" : "Download-Ready"})


@socketio.on('message')
def socket_bidirct(msg):

    if msg[0] != "User has connected!":
        url = session['video_link']
        t = Thread(target=start_preparation, args=(msg[0], url, msg[1],), daemon = True)
        t.start()
        
        while True:
            sleep(2)
            if status.get(msg[0]) == "Download-Ready":
                send("Download-Ready")
                break
        del status[msg[0]]
            
    if msg[0] == "User has connected!":
        print(msg[0])

@app.post('/yt-downloader/video/download')
def download_video():
    try:
        if file_data.get("status") == "Done":
            return send_file(file_data.get('bfr'), as_attachment=True, attachment_filename=file_data.get('fname'), mimetype="video/mp4")
    except Exception:
        return redirect(url_for('yt_video_downloader'))
        


@app.route('/yt-downloader/audio', methods=['GET', 'POST'])
def yt_audio_downloader():
    if request.method == 'POST':
        session['video_link'] = request.form.get('video-url')
        try:
            url = YouTube(session['video_link'])
            url.check_availability()
            return render_template('youtube/audio/download.html', url=url)
        except exceptions.MembersOnly:
            flash('Join this channel to get access to members-only content like this audio, and other exclusive perks.',
                  'error')
            return redirect(url_for('yt_audio_downloader'))
        except exceptions.RecordingUnavailable:
            flash('The audio recording is not available!', 'error')
            return redirect(url_for('yt_audio_downloader'))
        except exceptions.VideoPrivate:
            flash(
                'This is a private video and hence cannot get the audio. Please sign in to verify that you may see it.')
            return redirect(url_for('yt_audio_downloader'))
        except Exception as e:
            print(e)
            flash('Unable to fetch the video/audio from YouTube', 'error')
            return redirect(url_for('yt_audio_downloader'))

    return render_template('youtube/audio/audio.html', title='Download Audio')


@app.post('/yt-downloader/audio/download')
def download_audio():
    url = session['video_link']
    buffer, filename = yt.download_audio(url)
    return send_file(buffer, as_attachment=True, attachment_filename=f"{filename}.mp3", mimetype="audio/mp3")


@app.route('/yt-downloader/playlist', methods=['GET', 'POST'])
def yt_playlist_downloader():
    if request.method == 'POST':
        session['playlist_link'] = request.form.get('playlist-url')
        try:
            url = Playlist(session['playlist_link'])
            return render_template('youtube/playlist/download.html', url=url)
        except exceptions.MembersOnly:
            flash('Join this channel to get access to members-only content like this video, and other exclusive perks.',
                  'error')
            return redirect(url_for('yt_playlist_downloader'))
        except exceptions.RecordingUnavailable:
            flash('The video recording is not available!', 'error')
            return redirect(url_for('yt_playlist_downloader'))
        except exceptions.VideoPrivate:
            flash(
                'This is a private video. Please sign in to verify that you may see it.')
            return redirect(url_for('yt_playlist_downloader'), 'error')
        except Exception as e:
            print(e)
            flash('Unable to fetch the videos from YouTube Playlist', 'error')
            return redirect(url_for('yt_playlist_downloader'))

    return render_template('youtube/playlist/playlist.html', title='Download YouTube Playlist')


@app.post('/yt-downloader/playlist/download')
def download_playlist():
    url = Playlist(session['playlist_link'])
    for video in url.videos:
        video.streams.get_highest_resolution().download()

    return redirect(url_for('yt_playlist_downloader'))


@app.route('/yt-downloader/playlist/calculate', methods=['GET', 'POST'])
def calculate_playlist_duration():
    if request.method == 'POST':
        try:
            playlist_link = request.form.get('playlist-url')
            playlist_link = playlist_link.replace(
                "https://youtube", "https://www.youtube")
            playlist_link = playlist_link.replace(
                "https://m.youtube", "https://www.youtube")
            pl = Playlist(playlist_link)
            pl_obj = playlist.PlaylistCalculator(playlist_link)
            duration = pl_obj.get_duration_of_playlist([1, 1.25, 1.5, 1.75, 2])
            return render_template('youtube/duration/playlist.html', playlist=pl, duration=duration, result=True, title='Calculate Playlist Duration')
        except Exception:
            flash('Unable to fetch the videos from YouTube Playlist', 'error')
            return redirect(url_for('calculate_playlist_duration'))

    return render_template('youtube/duration/playlist.html', title='Calculate Playlist Duration')


@app.route('/ig-downloader/profile-pic', methods=['GET', 'POST'])
def ig_dp_downloader():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            filename = ig.download_profile_picture(username)
            file_path = os.path.join(os.path.abspath(username), filename)
            return_img = BytesIO()
            with open(file_path, 'rb') as fp:
                return_img.write(fp.read())
            return_img.seek(0)
            os.remove(file_path)
            os.removedirs(os.path.abspath(username))
            return send_file(return_img, mimetype='image/jpg', as_attachment=True, attachment_filename=f'{username}.jpg')
        except Exception as e:
            print(e)
            flash('Unable to fetch and download the profile picture, try again!', 'error')
            return redirect(url_for('ig_dp_downloader'))

    return render_template('instagram/profile_pic.html', title="Download Profile Picture")


@app.route('/ig-downloader/latest-stories', methods=['GET', 'POST'])
def ig_stories_downloader():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            filename = ig.download_latest_stories(username)
            with open(os.path.abspath(filename), 'rb') as fp:
                data = fp.readlines()
            os.remove(os.path.abspath(filename))
            return Response(
                data,
                headers={
                    'Content-Type': 'application/zip',
                    'Content-Disposition': f'attachment; filename={filename}'
                }
            )
        except Exception as e:
            print(e)
            flash('Unable to fetch and download the stories, try again!', 'error')
            return redirect(url_for('ig_stories_downloader'))

    return render_template('instagram/stories.html', title="Download Latest Stories")


@app.route('/ig-downloader/image', methods=['GET', 'POST'])
def ig_image_downloader():
    if request.method == 'POST':
        try:
            post_url = request.form.get('post-url')
            post_url = post_url.replace(
                "https://instagram", "https://www.instagram")
            post_url = post_url.replace(
                "https://m.instagram", "https://www.instagram")
            filename = ig.download_image(post_url)
            if filename:
                if 'jpg' in filename:
                    return_img = BytesIO()
                    with open(filename, 'rb') as fp:
                        return_img.write(fp.read())
                    return_img.seek(0)
                    os.remove(filename)
                    return send_file(return_img, mimetype='image/jpg', as_attachment=True, attachment_filename=filename)
                elif 'zip' in filename:
                    with open(os.path.abspath(filename), 'rb') as fp:
                        data = fp.readlines()
                    os.remove(os.path.abspath(filename))
                    return Response(
                        data,
                        headers={
                            'Content-Type': 'application/zip',
                            'Content-Disposition': f'attachment; filename={filename}'
                        }
                    )
            else:
                flash(
                    'Please make sure the account is not private and the post contains image only!', 'error')
                return redirect(url_for('ig_image_downloader'))
        except Exception as e:
            print(e)
            flash('Unable to fetch and download the profile picture, try again!', 'error')
            return redirect(url_for('ig_image_downloader'))

    return render_template('instagram/picture.html', title='Download Images')


@app.route('/ig-downloader/video', methods=['GET', 'POST'])
def ig_video_downloader():
    if request.method == 'POST':
        try:
            video_url = request.form.get('video-url')
            video_url = video_url.replace(
                "https://instagram", "https://www.instagram")
            video_url = video_url.replace(
                "https://m.instagram", "https://www.instagram")
            folder_name = ig.download_video(video_url)

            # Delete after sending

            for (dirpath, dirnames, filenames) in os.walk(os.path.abspath(folder_name)):
                if not 'temp' in filenames[0]:
                    return_video = BytesIO()
                    with open(os.path.join(os.path.abspath(folder_name), filenames[0]), 'rb') as fp:
                        return_video.write(fp.read())
                    return_video.seek(0)
                    shutil.rmtree(os.path.abspath(folder_name))
                    return send_file(return_video, as_attachment=True, attachment_filename=f'{folder_name}.mp4')
        except Exception as e:
            print(e)
            flash('Unable to fetch and download the video, try again!', 'error')
            return redirect(url_for('ig_video_downloader'))

    return render_template('instagram/video.html', title='Download Videos')


# Custom routes to check errors.
@app.route("/tos")
def tos():
    return render_template('tos.html', title='Terms of Service')


@app.route("/blogs")
def blog():
    posts = fetch_posts()
    return render_template('blog/blog.html', title='Blogs', posts=posts)


@app.get('/post/<id>/<slug>')
def single_page(id, slug):
    post = get_blog_post(id, slug)
    return render_template('blog/single.html', post=post, title=f"{post['fields']['title']}")


@app.route("/donate")
def donate():
    return render_template('donate.html', title='Make your donation now')


@app.errorhandler(NotFound)
def handle_not_found(e):
    return render_template('error/404.html', title="404 Not Found")


@app.errorhandler(InternalServerError)
def handle_internal_server_error(e):
    return render_template('error/500.html', title='500 Internal Server Error')


@app.errorhandler(MethodNotAllowed)
def method_not_allowed(e):
    return render_template('error/405.html', title="405 Method Not Allowed")


@app.get('/contributors')
def contributors_page():
    contributors = get_contributors()
    return render_template('contributors.html', title="Contributors", contributors=contributors)


@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    pages = []

    # get static routes
    # use arbitary 10 days ago as last modified date
    lastmod = datetime.now() - timedelta(days=10)
    lastmod = lastmod.strftime('%Y-%m-%d')
    for rule in current_app.url_map.iter_rules():
        # omit auth and admin routes and if route has parameters. Only include if route has GET method
        if 'GET' in rule.methods and len(rule.arguments) == 0 \
                and not rule.rule.startswith('/admin') \
                and not rule.rule.startswith('/auth') \
                and not rule.rule.startswith('/test'):
            pages.append([f'{request.url_root[:-1]}' + rule.rule, lastmod])

    sitemap_template = render_template(
        'sitemap/sitemap_template.xml', pages=pages)
    response = make_response(sitemap_template)
    response.headers['Content-Type'] = 'application/xml'
    return response
