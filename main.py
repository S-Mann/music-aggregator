from environs import Env
import itertools
from collections import OrderedDict
from datetime import datetime
from dateutil.parser import parse
import json
from jsmin import jsmin
import random
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
CONSIDER_WILDCARD_ARTIST_THRESHOLD = configs['CONSIDER_WILDCARD_ARTIST_THRESHOLD']
DISCOVER_RELATED_ARTIST_THRESHOLD = configs['DISCOVER_RELATED_ARTIST_THRESHOLD']
DISCOVER_RELATED_ARTIST_ONLY_POPULAR = configs['DISCOVER_RELATED_ARTIST_ONLY_POPULAR']
DISCOVER_RELATED_ARTIST_ONLY_POPULAR_THRESHOLD = configs[
    'DISCOVER_RELATED_ARTIST_ONLY_POPULAR_THRESHOLD']
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
wildcard_lookup_limit = int(
    artist_lookup_limit * CONSIDER_WILDCARD_ARTIST_THRESHOLD)
discover_related_artist_lookup_limit = int(
    wildcard_lookup_limit * DISCOVER_RELATED_ARTIST_THRESHOLD)
cut_off_artists = dict(itertools.islice(
    my_playlist_artists_ordered.items(), (artist_lookup_limit-wildcard_lookup_limit)))

if(wildcard_lookup_limit != 0):
    diffKeys = set(my_playlist_artists_ordered.keys()) - \
        set(cut_off_artists.keys())
    leftover_artists = dict()
    for key in diffKeys:
        leftover_artists[key] = my_playlist_artists_ordered.get(key)

    wildcard_artist_ids = list(leftover_artists.keys())
    top_artists_for_related = dict(itertools.islice(
        my_playlist_artists_ordered.items(), discover_related_artist_lookup_limit))
    top_artist_ids = list(top_artists_for_related.keys())
    for i in range(wildcard_lookup_limit):
        if(i > (wildcard_lookup_limit-discover_related_artist_lookup_limit)):
            top_artist_id = random.choice(top_artist_ids)
            results = spotify.artist_related_artists(top_artist_id)
            if len(results['artists']) > 0:
                related_artists = dict(
                    map(lambda i: (i['id'], i), results['artists']))
                if DISCOVER_RELATED_ARTIST_ONLY_POPULAR:
                    related_artists_sorted = OrderedDict(
                        sorted(related_artists.items(), key=lambda t: t[1]['popularity'], reverse=True))
                    top_related_artists = dict(itertools.islice(
                        related_artists_sorted.items(), int(len(related_artists_sorted)*DISCOVER_RELATED_ARTIST_ONLY_POPULAR_THRESHOLD)))
                    top_related_artist_ids = list(top_related_artists.keys())
                    random_related_artist_id = random.choice(
                        top_related_artist_ids)
                    random_related_artist = top_related_artists[random_related_artist_id]
                else:
                    related_artist_ids = list(related_artists.keys())
                    random_related_artist_id = random.choice(
                        related_artist_ids)
                    random_related_artist = related_artists[random_related_artist_id]
            while any(x in list(random_related_artist.keys()) for x in list(cut_off_artists.keys())):
                random_related_artist = random.choice(results['artists'])
            if random_related_artist:
                cut_off_artists[random_related_artist['id']
                                ] = random_related_artist
                cut_off_artists[random_related_artist['id']
                                ]['count'] = 0
            top_artist_ids.remove(top_artist_id)
            continue
        wildcard_artist_id = random.choice(wildcard_artist_ids)
        cut_off_artists[wildcard_artist_id] = leftover_artists[wildcard_artist_id]
        wildcard_artist_ids.remove(wildcard_artist_id)

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
