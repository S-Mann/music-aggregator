from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
from environs import Env

env = Env()
env.read_env()

CLIENT_ID = env("CLIENT_ID")
CLIENT_SECRET = env("CLIENT_SECRET")

chill_rap = 'spotify:playlist:6OkM4rqtPIsnDHDdL3oZU8'
spotify = spotipy.Spotify(
    client_credentials_manager=SpotifyClientCredentials(client_secret=CLIENT_SECRET, client_id=CLIENT_ID))

my_playlist = spotify.playlist(chill_rap)
# playlist_tracks(chill_rap, limit=LIMIT, offset=0)
songs = my_playlist['tracks']['items']
playlist_artists = {}
for song in songs:
    artists = song['track']['artists']
    for artist in artists:
        playlist_artists[artist['uri']] = artist['name']
        # TODO : Need to add count for each artist
