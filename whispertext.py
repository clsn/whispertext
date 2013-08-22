#!/usr/bin/env python

import os, threading
import sys
from telnetlib import Telnet
from md5 import md5
from libxml2 import parseDoc
from cmd import Cmd
import re
import readline

port=8338                       # Insecure connections.  I'm an insecure guy.

namelist={}
grouplist={}                    # Maybe eventually useful?
thread=None
logfd=None

def dataval(tree, tagname):
    # So many of these are the same, might as well abstract it.
    return tree.xpathEval('//'+tagname)[0].content


from xml.dom.minidom import getDOMImplementation

domimpl=getDOMImplementation()
def Request(command, **args):
    doc=domimpl.createDocument(None, "Request", None)
    cmd=doc.createElement('Command')
    txt=doc.createTextNode(command)
    cmd.appendChild(txt)
    doc.documentElement.appendChild(cmd)
    argselt=doc.createElement('Arguments')
    doc.documentElement.appendChild(argselt)
    for (arg, value) in args.iteritems():
        node=doc.createElement(arg)
        if value is not None:
            txt=doc.createTextNode(str(value))
            node.appendChild(txt)
        argselt.appendChild(node)
    return doc.toxml()

##############################################
# Requests
##########

class WhisCmd(Cmd):
    tn=None
    logfd=None

    # To get / commands, we need to tweak the incoming line.
    def precmd(self, line):
        if line.startswith('/'):
            match=re.match('/(\d+)(.*)', line)
            if line.startswith('//'):
                return 'say 0 ' + line[1:]
            elif match and match.group(1):
                return 'say ' + match.group(1) + ' ' + match.group(2)
            else:
                return line[1:] # expose the command
        else:
            return 'say 0 ' + line

    def sendit(self, txt):
        txt=txt.encode('utf-8')
        # print "\t"+outmsg
        self.tn.write(txt+"\n")
        if self.logfd:
            self.logfd.write(txt+"\n")
        print "\n"
        return None


    # Don't repeat yourself
    def emptyline(self, *args):
        return None

    def do_login(self,line):
        "Login firstname lastname password"
        args=line.split(' ',2)
        return self.sendit(Request("Login",
                                   FirstName=args[0],
                                   LastName=args[1],
                                   Password="$1$%s"%md5(args[2]).hexdigest(),
                                   StartLocation='last',
                                   SimName=None,
                                   X=None, Y=None, Z=None,
                                   ClientName='Whispering Fingers'))
    
    
    def do_logout(self,line):
        "Logout"
        return self.sendit(Request('Logout'))
    
    def do_friends(self,line):
        "FriendsList\nShow list of friends."
        return self.sendit(Request('FriendsList'))
    
    def completedefault(self, text, line, begidx, endidx):
        return [s for s in filter((lambda x: x.startswith(text)), [n.replace(' ','.') for n in namelist.keys()])]

    def do_im(self,line):
        "Im UUID Message\nIf a name is used instead of UUID, use firstname.lastname"
        [UUID, message]=line.split(' ',1)
        return self.sendit(Request('InstantMessageSend',
                                   UUID=namelist.get(UUID.replace("."," "), UUID),
                                   Message=message))

    
    def do_say(self,message):
        if not message.strip():
            raise ValueError
            return None         # Nothing to say.
        try:
            (channel, message)=message.split(' ', 1)
        except ValueError:
            channel="0"
        # Just in case
        if not channel.isdigit():
            message = channel + ' ' + message
            channel='0'
        message=message.strip()
        return self.sendit(Request('ChatSend',
                                   Message=message,
                                   Channel=channel,
                                   ChatType='normal'))
    
    def do_friendrequest(self,line):
        "Friendrequest UUID [message]\nSend Friend request to UUID (or firstname.lastname)"
        pieces=line.split(' ',1)
        UUID=namelist.get(pieces[0].replace(".", " "),pieces[0])
        try:
            message=pieces[1] or "Will you be my friend?"
        except IndexError:
            message="Will you be my friend?"
            return self.sendit(Request('FriendshipRequest',
                                       UUID=UUID,
                                       Message=message))
        
    def do_avatarprofile(self,UUID):
        "Avatarprofile UUID (or firstname.lastname)\nCheck if avatar is online."
        return self.sendit(Request('AvatarProfile',
                                   UUID=namelist.get(UUID.replace('.',' '),UUID)))
    
    def do_searchavatar(self,name):
        "Searchavatar name\nSearch for an avatar name."
        return self.sendit(Request('SearchAvatar',
                                   Name=name))
    
    def do_tpaccept(self,name):
        "Tpaccept UUID\nIf using name instead of UUID, use firstname.lastname"
        return self.sendit(Request('TeleportAccept',
                       UUID=namelist.get(name.replace('.', ' '),name)))

    def do_teleport(self,line):
        "Teleport X Y Z Sim"
        [x, y, z, sim]=line.split(' ',3) # Sim names can have spaces in them.
        return self.sendit(Request('TeleportLocal',
                                   X=x, Y=y, Z=z,
                                   SimName=sim))
    
    def do_tplure(self,line):
        "Tplure UUID [message]\nSend TP invite to UUID (or firstname.lastname)"
        [name, msg]=line.split(' ', 1)
        return self.sendit(Request('TeleportLure',
                                   UUID=namelist.get(name.replace('.',' '),name),
                                   Message=(msg or 'Please join me')))
    
    def do_location(self,line):
        "Location\nGet information about current location."
        return self.sendit(Request('CurrentLocation'))
    
    def do_home(self,line):
        "Home\nTeleport home"
        return self.sendit(Request('TeleportHome'))
    
    def do_accepttos(self,line):
        "Accepttos firstname lastname true/false"
        # Not needed often, but you can't log on without it when it's needed!
        [firstname, lastname, decision]=line.split(' ')
        return self.sendit(Request('AcceptTos',
                                   FirstName=firstname, LastName=lastname,
                                   Accept=decision))

    def do_namelist(self,line):
        "Namelist\nShow currently known list of names/UUIDs"
        shownamelist()

    def do_raw(self,line):
        "Raw <xml text>\nSend XML text unaltered."
        return self.sendit(line)

    def do_EOF(self, *args):
        "Exit"
        import sys
        print "Exiting."
        os.kill(os.getpid(),1)
        sys.exit(0)

    do_quit=do_EOF
    do_exit=do_EOF

##########################################################
# Responses
###########

def RespChat(tree):
    "Chat received"
    msg=dataval(tree,"Message")
    speaker=dataval(tree,"FromName")
    sourcetype=dataval(tree,"SourceType")
    if sourcetype=='Object':
        speaker="(%s)"%speaker
    elif sourcetype=='System':
        speaker='<%s>'%speaker
    return '[%s]: %s'%(speaker,msg)

def RespFriendsList(tree):
    "Friends list"
    friendlist=''
    for elt in tree.xpathEval("//Friend"):
        status=elt.xpathEval("Status")[0].content
        if status == 'Online':
            status += ' <== ***'
        friendlist+="\t%s\t%s\n"%(elt.xpathEval("Name")[0].content,
                                  status)
        namelist[elt.xpathEval("Name")[0].content]= \
            elt.xpathEval("UUID")[0].content
    return "Friends:\n%s"%friendlist

def RespInstantMessage(tree):
    "Instant Message received"
    msg=dataval(tree,"Message")
    speaker=dataval(tree,"Name")
    namelist[speaker]=dataval(tree,"UUID")
    return "[*IM* %s]: %s"%(speaker, msg)

def RespTeleportOffer(tree):
    "Teleport offer received"
    name=dataval(tree,"Name")
    msg=dataval(tree,"Message")
    return "((%s wants to teleport us somewhere: %s))"%(name, msg)

def RespDisconnect(tree):
    "Disconnected"
    return "Disconnected: %s (%s)"%(dataval(tree,"Reason"),
                                    dataval(tree,"Message"))

def RespMessageBox(tree):
    "Message box received"
    return "]] %s: %s"%(dataval(tree,"Severity"),
                        dataval(tree,"Message"))

def RespGroupMessage(tree):
    "Group message received"
    return "(Group message) %s: %s"%(dataval(tree,"Name"),
                                     dataval(tree,"Message"));

def RespGroupNotice(tree):
    "Group notice received"
    return "((Group Notice)): (%s) %s: %s"%(dataval(tree,"AgentName"),
                                            dataval(tree,"Subject"),
                                            dataval(tree,"Message"))

def RespCurrentLocation(tree):
    "Current location received"
    return "Location: %s (%s, %s, %s)"%(dataval(tree,"SimName"),
                                        dataval(tree,"X"),
                                        dataval(tree,"Y"),
                                        dataval(tree,"Z"))

def RespCurrentParcel(tree):
    "Current parcel info received"
    return "Parcel: %s"%dataval(tree,"Name")

def RespAvatarProfile(tree):
    "Avatar profile received"
    UUID=dataval(tree,"AvatarUUID")
    name=dataval(tree,"AvatarName")
    online=dataval(tree,"IsOnline")
    namelist[name]=UUID
    return "%s (%s) online: %s"%(name, UUID, online) # That's what I cared about anyway.

def RespAvatarStatusChange(tree):
    "Avatar status change notice received"
    UUID=dataval(tree,"UUID")
    name=dataval(tree,"Name")
    status=dataval(tree,"Status")
    namelist[name]=UUID
    return "> %s (%s) is now %s."%(name, UUID, status)

def RespAvatarSearchResult(tree):
    "Avatar search results received"
    rv="Avatar Search Results:\n"
    for elt in tree.xpathEval("//Result"):
        name=elt.xpathEval("Name")[0].content
        UUID=elt.xpathEval("UUID")[0].content
        namelist[name]=UUID
        rv+="\t%s (%s)\n"%(name, UUID)
    return rv

def RespGroupList(tree):
    "Group list received"
    # This shows up on every login, might as well format it.
    rv="Groups:\n"
    lineend=False;
    # Try for a 2-column effect.
    cols=(os.getenv('COLUMNS') or 80)
    width=(cols-10)/2
    for elt in tree.xpathEval("//Group"):
        grouplist[elt.xpathEval("Name")[0].content] = \
            elt.xpathEval("UUID")[0].content
        rv+=("     %-"+str(width)+"s")%elt.xpathEval("Name")[0].content
        if lineend:
            rv+="\n"
        lineend = not lineend
    return rv

def RespNearbyAvatar(tree):
    "Information about nearby avatar received"
    rv="Nearby Avatar:\n"
    namelist[dataval(tree,"Name")]=dataval(tree,"UUID")
    rv+="\tName:\t%s (%s)\n"%(dataval(tree,"Name"), dataval(tree,"UUID"))
    rv+="\t\tDistance:\t%s\n"%dataval(tree,"Distance")
    rv+="\t\tSex:\t\t%s\n"%dataval(tree,"Sex")
    rv+="\t\tPresent:\t%s\n"%dataval(tree, "Present")
    return rv

def RespBalanceChange(tree):
    "Balance change"
    return "Balance changed: %s\n"%dataval(tree,"Message")

def RqPong(line):
    "Pong"
    return Request('Pong')

def formatDefault(tree):
    return "((Ignoring: %s))"%(tree.xpathEval("/*/Reply")[0].content)
    # return tree.__str__()

##########################################################

def shownamelist():
    "Show the cache of name/UUID mapping known"
    print "Known names: "
    for (name, uuid) in namelist.iteritems():
        print "\t%s\t==\t%s"%(name, uuid)
    print

def keepReading(tn):
    "Loop reading"
    while True:
        z=tn.read_until("</Response>") # Block if necessary.
        presentResponse(z)
        if z.find("Ping")>=0:
            tn.write(RqPong(None)+"\n")

def completer(text, state):
    # print "Calling completer (%s,%d)"%(text,state)
    completions=[s[2:] for s in filter((lambda x: x.startswith('Rq'+text.title())),globals().keys())]
    completions+=[s for s in filter((lambda x: x.startswith(text)), [n.replace(' ','.') for n in namelist.keys()])]
    # print "(((%s)))"%str(completions)
    return completions[state]

def presentResponse(s):
    "Format (if possible) and show response received to user"
    if logfd:
        logfd.write(s+"\n")
    try:
        tree=parseDoc(s)
    except:
        return "!!! Parse Failed\n"+s+"!!!"
    repl=tree.xpathEval("/*/Reply")
    if not repl:
        return "!!! Unknown Message\n"+s+"!!!"
    resptype=repl[0].content
    handlers={
        'Error':
            (lambda tree: "!!Error: %s!!"%dataval(tree,"Error")),
        'TypingStatusChange': (lambda x: ''),
        'Ping': (lambda x: ''),
        }
    if globals().has_key("Resp"+resptype):
        todo=globals()["Resp"+resptype]
    else:
        todo=handlers.get(resptype,formatDefault)
    msg=None
    try:
        msg=todo(tree)
    except Exception as e:
        print "!Exception "+str(e)+"!: "+s
    if msg:
        print '%s\n=='%msg
        
if __name__ == '__main__':
    import re
    from getopt import getopt
    opts=getopt(sys.argv[1:], "l:")[0]
    logfd=None
    for opt in opts:
        if opt[0]=='-l':
            outname=opt[1]
            logfd=open(outname,"w") # w+?
#    if not logfd:
#        from datetime import datetime
#        outname=str(datetime.now())
#        logfd=open(outname,"w")
    tn=Telnet('localhost', port)
    readline.parse_and_bind('tab: complete')
    readline.parse_and_bind('C-l: redraw-current-line')
    readline.set_completer(completer)
    repl=WhisCmd()
    repl.tn=tn
    repl.logfd=logfd
    repl.prompt='>>> '
    thread=threading.Thread(target=keepReading, args=(tn,))
    thread.start()
    # Loop in a loop, lest an exception happen.
    while True:
        try:
            repl.cmdloop()
        except Exception as e:
            print "Exception: %s"%str(e)
