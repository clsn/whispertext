#!/usr/bin/env python

import os, threading
import sys
from telnetlib import Telnet
from md5 import md5
from libxml2 import parseDoc
import re

# There's a right way to do this.  I'm not doing it.

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

def RqLogin(line):
    "Login firstname lastname password"
    args=line.split(' ',2)
    return Request("Login",
                   FirstName=args[0],
                   LastName=args[1],
                   Password="$1$%s"%md5(args[2]).hexdigest(),
                   StartLocation='last',
                   SimName=None,
                   X=None, Y=None, Z=None,
                   ClientName='Whispering Fingers')


def RqLogout(line):
    "Logout"
    return Request('Logout')

def RqFriends(line):
    return Request('FriendsList')

def RqPong(line):
    return Request('Pong')

def RqIm(line):
    "Im UUID Message\nIf a name is used instead of UUID, use firstname.lastname"
    [UUID, message]=line.split(' ',1)
    return Request('InstantMessageSend',
                   UUID=namelist.get(UUID.replace("."," "), UUID),
                   Message=message)

def chatSend(message, channel=0):
    return Request('ChatSend',
                   Message=message,
                   Channel=channel,
                   ChatType='normal')

def friendRequest(UUID, message="Will you be my friend?"):
    "Friendrequest UUID [message]"
    return Request('FriendRequest',
                   UUID=UUID,
                   Message=message)

def avatarProfile(UUID):
    return Request('AvatarProfile',
                   UUID=namelist.get(UUID.replace('.',' '),UUID))

def RqSearch(name):
    "Search name"
    return Request('SearchAvatar',
                   Name=name)

def RqTpaccept(name):
    "Tpaccept UUID\nIf using name instead of UUID, use firstname.lastname"
    return Request('TeleportAccept',
                   UUID=namelist.get(name.replace('.', ' '),name))

def RqTeleport(line):
    "Teleport Sim X Y Z"
    [sim, x, y, z]=line.split(' ')
    return Request('TeleportLocal',
                   X=x, Y=y, Z=z,
                   SimName=sim)

def RqTplure(line):
    "Tplure UUID [message]"
    [name, msg]=line.split(' ', 1)
    return Request('TeleportLure',
                   UUID=namelist.get(name.replace('.',' '),name),
                   Message=(msg or 'Please join me'))

def RqLocation(line):
    return Request('CurrentLocation')

def RqHome(line):
    return Request('TeleportHome')

def RqAccepttos(line):
    "Accepttos firstname lastname true/false"
    [firstname, lastname, decision]=line.split(' ')
    return Request('AcceptTos',
                   FirstName=firstname, LastName=lastname,
                   Accept=decision)

##########################################################
# Responses
###########

def RespChat(tree):
    msg=dataval(tree,"Message")
    speaker=dataval(tree,"FromName")
    sourcetype=dataval(tree,"SourceType")
    if sourcetype=='Object':
        speaker="(%s)"%speaker
    elif sourcetype=='System':
        speaker='<%s>'%speaker
    return '[%s]: %s'%(speaker,msg)

def RespFriendsList(tree):
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
    msg=dataval(tree,"Message")
    speaker=dataval(tree,"Name")
    namelist[speaker]=dataval(tree,"UUID")
    return "[*IM* %s]: %s"%(speaker, msg)

def RespTeleportOffer(tree):
    name=dataval(tree,"Name")
    msg=dataval(tree,"Message")
    return "((%s wants to teleport us somewhere: %s))"%(name, msg)

def RespDisconnect(tree):
    return "Disconnected: %s (%s)"%(dataval(tree,"Reason"),
                                    dataval(tree,"Message"))

def RespMessageBox(tree):
    return "]] %s: %s"%(dataval(tree,"Severity"),
                        dataval(tree,"Message"))

def RespGroupMessage(tree):
    return "(Group message) %s: %s"%(dataval(tree,"Name"),
                                     dataval(tree,"Message"));

def RespGroupNotice(tree):
    return "((Group Notice)): (%s) %s: %s"%(dataval(tree,"Name"),
                                            dataval(tree,"Subject"),
                                            dataval(tree,"Message"))

def RespCurrentLocation(tree):
    return "Location: %s (%s, %s, %s)"%(dataval(tree,"SimName"),
                                        dataval(tree,"X"),
                                        dataval(tree,"Y"),
                                        dataval(tree,"Z"))

def RespCurrentParcel(tree):
    return "Parcel: %s"%dataval(tree,"Name")

def RespAvatarProfile(tree):
    UUID=dataval(tree,"AvatarUUID")
    name=dataval(tree,"AvatarName")
    online=dataval(tree,"IsOnline")
    namelist[name]=UUID
    return "%s (%s) online: %s"%(name, UUID, online) # That's what I cared about anyway.

def RespAvatarStatusChange(tree):
    UUID=dataval(tree,"UUID")
    name=dataval(tree,"Name")
    status=dataval(tree,"Status")
    namelist[name]=UUID
    return "> %s (%s) is now %s."%(name, UUID, status)

def RespAvatarSearchResult(tree):
    rv="Avatar Search Results:\n"
    for elt in tree.xpathEval("//Result"):
        name=elt.xpathEval("Name")[0].content
        UUID=elt.xpathEval("UUID")[0].content
        namelist[name]=UUID
        rv+="\t%s (%s)\n"%(name, UUID)
    return rv

def RespGroupList(tree):
    # This shows up on every login, might as well format it.
    rv="Groups:\n"
    lineend=False;
    # Try for a 2-column effect.
    for elt in tree.xpathEval("//Group"):
        grouplist[elt.xpathEval("Name")[0].content] = \
            elt.xpathEval("UUID")[0].content
        rv+="\t"+elt.xpathEval("Name")[0].content
        if lineend:
            rv+="\n"
        lineend = not lineend
    return rv

def formatDefault(tree):
    return tree.__str__()

##########################################################

def shownamelist():
    print "Known names: "
    for (name, uuid) in namelist.iteritems():
        print "\t%s\t==\t%s"%(name, uuid)
        print

def keepReading(tn):
    while True:
        z=tn.read_until("</Response>") # Block if necessary.
        presentResponse(z)
        if z.find("Ping")>=0:
            tn.write(RqPong(None)+"\n")

def Quit(*args):
    import sys
    print "Exiting, right??"
    os.kill(os.getpid(),1)
    sys.exit(0)

def presentResponse(s):
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
        # Should have side effect of learning UUIDs
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
        print '==\n%s\n=='%msg
        
if __name__ == '__main__':
    import re
    from getopt import getopt
    opts=getopt(sys.argv[1:], "l:")[0]
    logfd=None
    for opt in opts:
        if opt[0]=='-l':
            outname=opt[1]
            logfd=open(outname,"w") # w+?
    if not logfd:
        from datetime import datetime
        outname=str(datetime.now())
        logfd=open(outname,"w")
    tn=Telnet('localhost', port)
    while True:
        try:
            if not thread or not thread.isAlive():
                thread=threading.Thread(target=keepReading, args=(tn,))
                thread.start()
            line=sys.stdin.readline() # no strip; trailing spaces might be needed.
            # But lose the newline.
            line=line[:-1]
            channel=0
            match=re.match('(/?/?)(\d*\s*)(.*)', line)
            if match.group(1)=='/':
                if match.group(2):
                    channel=int(match.group(2))
                    cmd='Say'
                    rest=match.group(3)
                else:
                    # A little legerdemain to get the right size
                    [cmd,rest]=(match.group(3).split(' ',1)+[''])[:2]
            elif match.group(1)=='//':
                cmd='Say'
                rest=line[1:]
            else:
                cmd='Say'
                rest=line
            outmsg=None
            rq="Rq"+cmd.title()
            if globals().has_key(rq):
                outmsg=(globals()[rq])(rest)
            elif cmd == 'namelist':
                shownamelist()
                continue
            elif cmd in ['Quit', 'Exit', 'quit', 'exit']:
                    Quit()
            elif cmd == 'Say':
                if not rest:    # Nothing to say.
                    continue
                outmsg = chatSend(rest, channel)
            else:
                print "??"
                outmsg=cmd          # Escape clause to type whatever we want.
            if outmsg:
                outmsg=outmsg.encode('utf-8')
                print "\t"+outmsg
                tn.write(outmsg+"\n")
                if logfd:
                    logfd.write(outmsg+"\n")
                print "\n"
            print "---\n"
        except Exception as e:
            print "Exception in I/O: " + str(e)
        except KeyboardInterrupt as e:
            print "Keyboard Interrupt: "+str(e)
