# -*- coding: utf-8 -*-
from __future__ import absolute_import

__kupfer_name__ = _("music player daemon")
__kupfer_sources__ = ("MpdAlbumSource",)
__kupfer_actions__ = ("PlayAlbum","EnqueueAlbum",)
__description__ = _("control mpd from kupfer")
__version__ = "0.1"
__author__ = ("Rene Milk <koshi@springlobby.info>" )

import subprocess

from kupfer.objects import Action, Source, Leaf
from kupfer.objects import TextLeaf
from kupfer.obj.grouping import ToplevelGroupingSource
from kupfer import icons, kupferstring, task, uiutils, utils
from kupfer import plugin_support, pretty
import mpd
from socket import error as SocketError

__kupfer_settings__  = plugin_support.PluginSettings(
	{
		"key": "mpd_host",
		"label": _("Mpd host"),
		"type": str,
		"value": "localhost",
		"tooltip": _("The hostname of your mpd")
	},
	{
		"key": "mpd_port",
		"label": _("Port"),
		"type": str,
		"value": "6600",
		"tooltip": _("Mpd port number")
	},
	{
		"key": "mpd_password",
		"label": _("Password"),
		"type": str,
		"value": "",
		"tooltip": _("Leave blank of your mpd does not require a password")
	},
)

def uniqify(seq, idfun=None):  
	# order preserving 
	if idfun is None: 
		def idfun(x): return x 
	seen = {} 
	result = [] 
	for item in seq: 
		marker = idfun(item) 
		# in old Python versions: 
		# if seen.has_key(marker) 
		# but in new ones: 
		if marker in seen: continue 
		seen[marker] = 1 
		result.append(item) 
	return result
	
## Some functions
def mpdConnect(client):
	"""
	Simple wrapper to connect MPD.
	"""
	try:
		con_id = {'host':__kupfer_settings__["mpd_host"], 'port':str(__kupfer_settings__["mpd_port"])}
		client.connect(**con_id)
	except SocketError:
		return False
	return True

def mpdAuth(client):
	"""
	Authenticate
	"""
	try:
		pw = __kupfer_settings__["mpd_password"]
		if not pw == "":
			client.password(pw)
	except mpd.CommandError:
		return False
	return True
##

def getClient():
	client = mpd.MPDClient()
	if mpdConnect(client) and mpdAuth(client):
		pretty.print_debug(__name__, 'Got connected!')
	else:
		pretty.print_debug(__name__, 'fail to connect MPD server.')
	return client

class Album(dict):
	def __init__(self,title,artist,all_file_infos):
		super(dict,self).__init__()
		if isinstance(title,list):
			self.__setitem__('title',title[0])
		else:
			self.__setitem__('title',title)
		if isinstance(artist,list):
			self.__setitem__('artist', artist[0] )
		else:
			self.__setitem__('artist', artist )
		self.all_file_infos = all_file_infos

	@property
	def title(s):
		return s.__getitem__('title')
	@property
	def artist(s):
		return s.__getitem__('artist')
	@property
	def files(self):
		for x in filter( lambda y: y['album'] == self.title and y['artist'] == self.artist, self.all_file_infos):
			yield x['file'] 

	def __getitem__(self,key):
		if key == 'files':
			return ' '.join([x['file'] for x in filter( lambda y: y['album'] == self.title and y['artist'] == self.artist, self.all_file_infos) ])
		return dict.__getitem__(self,key)
		
	def __str__(self):
		return "%s -- %s (Album)\n\t%s"%(self.artist,self.title,' | '.join(self.files) )
	def __repr__(self):
		return "%s -- %s (Album)"%(self.artist,self.title)

	#these are necessary for uniqify
	def __eq__(s,o):
		return s.__dict__ == o.__dict__
	def __hash__(self):
		return hash(self.title + self.artist)
		
class AlbumLeaf (Leaf):
	def __init__(self, album):
		Leaf.__init__(self, album, album.title)
		self._album = album
		
	@property
	def album(self):
		return self._album
		
	def get_icon_name(self):
		return "media-optical"
	def __hash__(self):
		return self._album.__hash__()

	def __eq__(self, other):
		return (isinstance(other, type(self)) and
				self._album == other.album)
		
class AlbumAction (Action):
	def __init__(self,clear, name):
		Action.__init__(self, name)
		self.clear = clear
	def activate(self, leaf):
		self.activate_multiple((leaf, ))
	def get_icon_name(self):
		return "media-playback-start"	
	def item_types(self):
		yield AlbumLeaf
	def activate_multiple(self, leafs):
		client = getClient()
		if self.clear:
			client.clear()
		for leaf in leafs:
			for track in leaf.album.files:
				client.add( track )
		if self.clear:
			client.play()
		
class PlayAlbum (AlbumAction):
	def __init__(self):
		AlbumAction.__init__(self, True, name=_("Play"))
		
	def get_description(self):
		return _("Play Album")

class EnqueueAlbum (AlbumAction):
	def __init__(self):
		AlbumAction.__init__(self, False, name=_("Enqueue"))
		
	def get_description(self):
		return _("Enqueue Album")

class MpdAlbumSource (Source):
	def __init__(self):
		Source.__init__( self, _("Albums"))

	def get_items(self):
		client = getClient()
		file_infos = [client.listallinfo(x['file'])[0] for x in filter( lambda x: 'file' in x , client.listall() ) ]
		filtered_file_infos = filter( lambda f: 'artist' in f and 'album' in f , file_infos)
		albums = [Album(x['album'],x['artist'],filtered_file_infos) for x in filtered_file_infos ]
		albums.sort()
		pretty.print_debug(__name__, 'Got %d items'%len(albums) )
		for album in uniqify(albums):
			yield AlbumLeaf(album)

	def should_sort_lexically(self):
		return False

	def get_description(self):
		return _("Music albums in mpd Library")
	def get_icon_name(self):
		return "applications-internet"
	def provides(self):
		yield AlbumLeaf