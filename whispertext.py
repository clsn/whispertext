#!/usr/bin/env python

import os, threading
import sys
from telnetlib import Telnet
from md5 import md5
from libxml2 import parseDoc

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

def loginmsg(firstname, lastname, password):
    return Request("Login",
                   FirstName=firstname,
                   LastName=lastname,
                   Password="$1$%s"%md5(password).hexdigest(),
                   StartLocation='last',
                   SimName=None,
                   X=None, Y=None, Z=None,
                   ClientName='Whispering Fingers')


logoutmsg=Request('Logout')

friendslistmsg=Request('FriendsList')

pongmsg=Request('Pong')

def instantMessage(UUID, message):
    return Request('InstantMessageSend',
                   UUID=namelist.get(UUID.replace("*"," "), UUID),
                   Message=message)

def chatSend(message, channel=0):
    return Request('ChatSend',
                   Message=message,
                   Channel=channel,
                   ChatType='normal')

def friendRequest(UUID, message="Will you be my friend?"):
    return Request('FriendRequest',
                   UUID=UUID,
                   Message=message)

def avatarProfile(UUID):
    return Request('AvatarProfile',
                   UUID=namelist.get(UUID.replace('*',' '),UUID))

def avsearchmsg(name):
    return Request('SearchAvatar',
                   Name=name)

def tpacceptmsg(name):
    return Request('TeleportAccept',
                   UUID=namelist.get(UUID.replace('*', ' '),UUID))

def teleportmsg(sim, x, y, z):
    return Request('TeleportLocal',
                   X=x, Y=y, Z=z,
                   SimName=sim)

def tpluremsg(UUID, msg="Please join me"):
    return Request('TeleportLure',
                   UUID=namelist.get(UUID.replace('*',' '),UUID),
                   Message=(msg or 'Please join me'))

currentLocationmsg=Request('CurrentLocation')

gohomemsg=Request('TeleportHome')

def acceptTos(firstname, lastname, decision):
    return Request('AcceptTos',
                   FirstName=firstname, LastName=lastname,
                   Accept=decision)

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
            tn.write(pongmsg+"\n")

def formatChat(tree):
    msg=dataval(tree,"Message")
    speaker=dataval(tree,"FromName")
    sourcetype=dataval(tree,"SourceType")
    if sourcetype=='Object':
        speaker="(%s)"%speaker
    elif sourcetype=='System':
        speaker='<%s>'%speaker
    return '[%s]: %s'%(speaker,msg)

def formatFriendsList(tree):
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

def formatIM(tree):
    msg=dataval(tree,"Message")
    speaker=dataval(tree,"Name")
    namelist[speaker]=dataval(tree,"UUID")
    return "[*IM* %s]: %s"%(speaker, msg)

def formatTPoffer(tree):
    name=dataval(tree,"Name")
    msg=dataval(tree,"Message")
    return "((%s wants to teleport us somewhere: %s))"%(name, msg)

def formatDisconnect(tree):
    return "Disconnected: %s (%s)"%(dataval(tree,"Reason"),
                                    dataval(tree,"Message"))

def formatMessageBox(tree):
    return "]] %s: %s"%(dataval(tree,"Severity"),
                        dataval(tree,"Message"))

def formatGroupMessage(tree):
    return "(Group message) %s: %s"%(dataval(tree,"Name"),
                                     dataval(tree,"Message"));

def formatGroupNotice(tree):
    return "((Group Notice)): (%s) %s: %s"%(dataval(tree,"Name"),
                                            dataval(tree,"Subject"),
                                            dataval(tree,"Message"))

def formatLocation(tree):
    return "Location: %s (%s, %s, %s)"%(dataval(tree,"SimName"),
                                        dataval(tree,"X"),
                                        dataval(tree,"Y"),
                                        dataval(tree,"Z"))

def formatParcel(tree):
    return "Parcel: %s"%dataval(tree,"Name")

def formatProfile(tree):
    UUID=dataval(tree,"AvatarUUID")
    name=dataval(tree,"AvatarName")
    online=dataval(tree,"IsOnline")
    namelist[name]=UUID
    return "%s (%s) online: %s"%(name, UUID, online) # That's what I cared about anyway.

def formatAvStatusChange(tree):
    UUID=dataval(tree,"UUID")
    name=dataval(tree,"Name")
    status=dataval(tree,"Status")
    namelist[name]=UUID
    return "> %s (%s) is now %s."(name, UUID, status)

def formatAvSearch(tree):
    rv="Avatar Search Results:\n"
    for elt in tree.xpathEval("//Result"):
        name=elt.xpathEval("Name")[0].content
        UUID=elt.xpathEval("UUID")[0].content
        namelist[name]=UUID
        rv+="\t%s (%s)\n"%(name, UUID)
    return rv

def formatGroupList(tree):
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
        'AvatarStatusChange':
            (lambda tree: "<<"+dataval(tree,"Name") + " is " + \
                 dataval(tree,"Status")+">>"),
        'Chat': formatChat,
        'Error':
            (lambda tree: "!!Error: %s!!"%dataval(tree,"Error")),
        # Should have side effect of learning UUIDs
        'FriendsList': formatFriendsList,
        'InstantMessage': formatIM,
        'TeleportOffer': formatTPoffer,
        # Trap this mostly so we can at least silence it.
        'TypingStatusChange': (lambda x: ''),
        'Disconnect': formatDisconnect,
        'MessageBox': formatMessageBox,
        'GroupMessage': formatGroupMessage,
        'GroupNotice': formatGroupNotice,
        'CurrentLocation': formatLocation,
        'CurrentParcel': formatParcel,
        'AvatarStatusChange': formatAvStatusChange,
        'AvatarProfile': formatProfile,
        'Ping': (lambda x: ''),
        }
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
            line=sys.stdin.readline().strip()
            args=line.split(" ")
            cmd=args[0]
	    # Extend by '' to avoid exception if too short.
	    linetail=(line.split(" ",2)+['',''])[2]
            outmsg=None
            if cmd == 'Login':
                outmsg=loginmsg(*args[1:])
            elif cmd == 'namelist': # lowercase: local command.
                shownamelist()
                continue
            elif cmd == 'Logout':
                outmsg=logoutmsg
            elif cmd == 'Friends':
                outmsg = friendslistmsg
            elif cmd == 'IM':
                outmsg = instantMessage(args[1],linetail)
            elif cmd == 'Home':
                outmsg=gohomemsg
            elif cmd == 'Pong':
                outmsg=pongmsg
            elif cmd == 'Location':
                outmsg=currentLocationmsg
            elif cmd == 'Search':
                outmsg=avsearchmsg(line.split(' ',1)[1])
            elif cmd == 'TPAccept':
                outmsg=tpacceptmsg(args[1])
            elif cmd == 'Teleport':
                outmsg=teleportmsg(args[1], args[2], args[3], args[4]) # sim, x, y, z
            elif cmd == 'TPLure':
                # Extending by [''] to prevent exception if not enough data
                outmsg=tpluremsg(args[1], linetail)
            elif cmd == 'AcceptTos':
                outmsg=acceptTos(args[1], args[2], args[3])
            elif cmd in ['Quit', 'Exit']:
                Quit()
            elif re.match(r'(\d*)Say',cmd):
                outmsg = chatSend(line.split(' ',1)[1], 
                                  (int(re.match(r'(\d*)Say',cmd).group(1)) or 0))
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
