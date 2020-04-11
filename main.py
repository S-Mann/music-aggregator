from environs import Env
import itertools
from collections import OrderedDict
from datetime import datetime
from dateutil.parser import parse
import json
from jsmin import jsmin
import spotipy

env = Env()
env.read_env()

CLIENT_ID = env("CLIENT_ID")
CLIENT_SECRET = env("CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = env("SPOTIPY_REDIRECT_URI")
with open('config.jsonc') as js_file:
    minified = jsmin(js_file.read())
configs = json.loads(minified)
ARTIST_THRESHOLD = configs['ARTIST_THRESHOLD']
PLAYLIST_URI = configs['PLAYLIST_URI']
USERNAME = configs['USERNAME']
DAYS_LIMIT = configs['DAYS_LIMIT']
GENERATED_PLAYLIST_NAME = configs['GENERATED_PLAYLIST_NAME']
GENERATED_PLAYLIST_IS_PUBLIC = configs['GENERATED_PLAYLIST_IS_PUBLIC']
GENERATED_PLAYLIST_DESCRIPTION = configs['GENERATED_PLAYLIST_DESCRIPTION']


LIMIT = 100
scope = 'playlist-modify-public'
token = spotipy.util.prompt_for_user_token(USERNAME,
                                           scope,
                                           client_id=CLIENT_ID,
                                           client_secret=CLIENT_SECRET,
                                           redirect_uri=SPOTIPY_REDIRECT_URI)
spotify = spotipy.Spotify(auth=token)

results = spotify.playlist_tracks(PLAYLIST_URI, limit=LIMIT, offset=0)
my_playlist_songs = results.get('items')
while results.get('next') and my_playlist_songs:
    results = spotify.next(results)
    my_playlist_songs.extend(results.get('items'))

my_playlist_artists = {}
for song in my_playlist_songs:
    artists = song['track']['artists']
    for artist in artists:
        my_artist = my_playlist_artists.get(artist['id'], None)
        if my_artist:
            my_artist['count'] += 1
        else:
            my_playlist_artists[artist['id']] = artist
            my_playlist_artists[artist['id']]['count'] = 1

my_playlist_artists_ordered = OrderedDict(
    sorted(my_playlist_artists.items(), key=lambda t: t[1]['count'], reverse=True))

artist_lookup_limit = int(len(my_playlist_artists_ordered) * ARTIST_THRESHOLD)
cut_off_artists = dict(itertools.islice(
    my_playlist_artists_ordered.items(), artist_lookup_limit))

latest_stuff = []
time_now = datetime.now()
for artist_id, artist in cut_off_artists.items():
    album_uris = []
    latest_albums = spotify.artist_albums(
        artist_id=artist_id, album_type='album', limit=1)
    for album in latest_albums['items']:
        release_date = parse(album['release_date'])
        if (time_now - release_date).days <= DAYS_LIMIT:
            album_uris.append(album['uri'])
    latest_single = spotify.artist_albums(
        artist_id=artist_id, album_type='single', limit=1)
    for single in latest_single['items']:
        release_date = parse(single['release_date'])
        if (time_now - release_date).days <= DAYS_LIMIT:
            album_uris.append(single['uri'])
    if len(album_uris) == 0:
        continue
    results = spotify.albums(albums=album_uris)
    for album in results['albums']:
        track_results = spotify.album_tracks(album['uri'])
        for item in track_results['items']:
            latest_stuff.append(item)
created_playlist = spotify.user_playlist_create(
    user=USERNAME, name=GENERATED_PLAYLIST_NAME, public=GENERATED_PLAYLIST_IS_PUBLIC, description=GENERATED_PLAYLIST_DESCRIPTION)
spotify.user_playlist_follow_playlist(
    playlist_owner_id=USERNAME, playlist_id=created_playlist['id'])
for i in range(0, len(latest_stuff), LIMIT):
    spotify.user_playlist_add_tracks(user=USERNAME, playlist_id=created_playlist['id'], tracks=[
        track['uri'] for track in latest_stuff[i:i+LIMIT]])
