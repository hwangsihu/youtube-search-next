from youtubesearchpython.search import Search, VideosSearch, ChannelsSearch, PlaylistsSearch, CustomSearch, ChannelSearch
from youtubesearchpython.extras import Video, Playlist, Suggestions, Hashtag, Comments, Transcript, Channel
from youtubesearchpython.streamurlfetcher import StreamURLFetcher
from youtubesearchpython.core.constants import *
from youtubesearchpython.core.utils import *


__title__        = 'youtube-search-next'
__version__      = '1.0.1'
__author__       = 'hwangsihu'
__license__      = 'MIT'


''' Deprecated. Present for legacy support. '''
from youtubesearchpython.legacy import SearchVideos, SearchPlaylists
from youtubesearchpython.legacy import SearchVideos as searchYoutube
