# Whispertext

Whispertext (name possibly subject to change) is a *true* text-only Second-Life viewer.  Some others that claim to be text-only are indeed non-graphical, but when I hear "text-only" I expect something that will run in text mode, no graphic support needed, no fancy windows, *just text*.

Whispertext relies upon the Whisper library (http://sourceforge.net/projects/slxslchat/) by Thomas Pedley for actual connection to the server.  Whisper provides XML events for all the various happenings in-world; whispertext merely interprets and provides a slightly more readable and writable interface.

Right now it's very messy, with most stuff ignored and only a few commands supported.  But it's a start.

## Commands

The commands in Whispertext should work pretty much as you're used to from existing clients: Type something to say it, except for commands which are preceded by a slash (/).  There are a few quirks at this point, though; see below for those.

Some commands supported by Whispertext:

* `/login Firstname Lastname Password`
* `/logout`
* `/friends`

	List your friends and their online status.  This adds all your friends to the "known UUIDs" list.
	
* `/im Firstname.Lastname Message`

	Note using . to separate first name from last name.  If the system doesn't already "know" the person's UUID you need to type the UUID of the person instead, if for some reason you know it.  Receiving an IM from someone adds that name to the "known UUIDs" list.
	
* `/friendrequest Firstname.Lastname [Message]`

	Request friendship.  If the name isn't in the "known UUIDs" list, you need to use the person's UUID.
	
* `/avatarprofile Firstname.Lastname`

	Requests the avatar's profile, but really only shows you the online status.  As above, you have to use the UUID if the system does not already know the UUID.  Checking someone's status this way adds that person to the "known UUIDs" list.
	
* `/searchavatar Name`

	Run a search for an avatar named "Name".  Any avatars found will be added to the "known UUIDs" list.
	
* `/tpaccept Firstname.Lastname`

	Accept a teleport offer from the named avatar.
	
* `/teleport X Y Z Simname`

	Attempt to teleport to the given X, Y, Z coordinates in the named sim.
	
* `/tplure Firstname.Lastname`

	Send a teleport offer to the named avatar.  If the avatar is not on the "known UUIDs" list you need to use the UUID instead of the name.
	
* `/location`

	Request information concerning your current location (coordinates and sim name).
	
* `/home`

	Teleport home
	
* `/accepttos Firstname Lastname true/false`

	If the server sends a "TOS Update" message when you log on, you need to accept the new TOS before you can continue logging on.  To see the new terms, do this in a real viewer. :)  If you just want to accept the terms, do `/accepttos FirstName LastName true`.  Use your avatar's first name and last name, with a space in between.

* `/[number] text...`

	Say the text on channel [number] (don't type the brackets).  This is the same as on the standard clients.
	
* `//me text...`

	This one is slightly different from the standard; in order to start with "/me" (for emotes), or anything that starts with a slash, you need to use two slashes instead.

* `/quit`

	(or `/exit`) quits Whispertext.  You should `/logout` first.

* `/namelist`

	Displays the current list of "known UUIDs".

* `/raw <XML doc>`

	Sends the XML text directly to the Whisper server, for debugging purposes in case we want to type in the XML by hand.

## Responses

Responses are messages from the SL server (via Whisper), not necessarily in direct response to something you did.  Whispertext "handles" a response mainly by just formatting it so you can read it.  Anything it can't format it will display as "Ignored" with the type of response, so you can see what it's ignoring (mainly useful for telling when the system is waiting for you to accept the new TOS).  A few responses are not formatted or displayed at all: the "Ping" response, which is a request for the client to send back a "Pong" (Whispertext does send back the Pong, but doesn't bother to show you the Ping), and responses that inform you when someone has started or stopped typing.

## Editing and Auto-Completion

Whispertext uses python's version of the readline library to provide you with access to your history (arrow-keys, ^P, ^N, etc) and editing.  There is also some rudimentary auto-complete enabled, where pressing TAB will attempt to complete either a /command or one of the "known" avatar names.  This can be handy when holding an IM conversation; you don't have to retype the person's name each time, just begin it and hit TAB.
