#!/usr/bin/env python

from data2XML import data2XML
import os, threading
import sys
from telnetlib import Telnet
from md5 import md5
from libxml2 import parseDoc

# There's a right way to do this.  I'm not doing it.

port=8338                       # Insecure connections.  I'm an insecure guy.

pongmsg=data2XML({'Request' : [
            { 'Command' : "Pong" },
            { 'Arguments': None } ]}).toxml()

namelist={}
thread=None

def loginmsg(firstname, lastname, password):
    return data2XML(
        {'Request' : [
                { 'Command' : 'Login' },
                { 'Arguments' : [
                        { 'FirstName': firstname },
                        { 'LastName' : lastname },
                        { 'Password' : "$1$%s"%md5(password).hexdigest() },
                        { 'StartLocation' : 'last' },
                        { 'SimName' : None },
                        { 'X' : None },
                        { 'Y' : None },
                        { 'Z' : None },
                        { 'ClientName' : 'Whispering Fingers' }
                        ]
                  }
                ]
         }).toxml()

logoutmsg=data2XML({'Request' : [
            { 'Command' : 'Logout' },
            { 'Arguments' : None }
            ]}).toxml()

friendslistmsg=data2XML(
    {'Request' : [
            {'Command' : 'FriendsList'},
            {'Arguments': None }
            ]
     }).toxml()

def instantMessage(UUID, message):
    return data2XML(
        {'Request': [
                { 'Command': 'InstantMessageSend' },
                { 'Arguments' : [
                        { 'UUID': namelist.get(UUID.replace("*"," "), UUID) },
                        { 'Message': message }
                        ]
                  }
                ]
         }).toxml()

def chatSend(message, channel=0):
    return data2XML(
        {'Request': [
                { 'Command' : 'ChatSend'},
                { 'Arguments' : [
                        { 'Message': message },
                        { 'Channel': channel },
                        { 'ChatType': 'Normal' }
                        ]
                  }
                ]
         }).toxml()

def friendRequest(UUID, message="Will you be my friend?"):
    return data2XML(
        {'Request': [
                { 'Command' : 'FriendRequest' },
                { 'Arguments' : [
                        { 'UUID' : UUID },
                        { 'Message': message}
                        ]
                  }
                ]
         }).toxml()

currentLocationmsg=data2XML(
    {'Request': [
            {'Command': 'CurrentLocation' },
            {'Arguments': None}
            ]}).toxml()

gohomemsg=data2XML(
    {'Request': [
            { 'Command': 'TeleportHome' },
            { 'Arguments': None}
            ]}).toxml()


def keepReading(tn):
    while True:
        z=tn.read_until("</Response>") # Block if necessary.
        presentResponse(z)
        if z.find("Ping")>=0:
            tn.write(pongmsg+"\n")

def formatChat(tree):
    msg=tree.xpathEval("//Message")[0].content
    speaker=tree.xpathEval("//FromName")[0].content
    sourcetype=tree.xpathEval("//SourceType")[0].content
    if sourcetype=='Object':
        speaker="(%s)"%speaker
    elif sourcetype=='System':
        speaker='<%s>'%speaker
    return '[%s]: %s'%(speaker,msg)

def formatFriendsList(tree):
    friendlist=''
    for elt in tree.xpathEval("//Friend"):
        friendlist+="\t%s\t%s\n"%(elt.xpathEval("Name")[0].content,
                                  elt.xpathEval("Status")[0].content)
        namelist[elt.xpathEval("Name")[0].content]= \
            elt.xpathEval("UUID")[0].content
    return "Friends:\n%s"%friendlist

def formatIM(tree):
    msg=tree.xpathEval("//Message")[0].content
    speaker=tree.xpathEval("//Name")[0].content
    return "[*IM* %s]: %s"%(speaker, msg)

def formatTPoffer(tree):
    name=tree.xpathEval("//Name")[0].content
    msg=tree.xpathEval("//Message")[0].content
    return "((%s wants to teleport us somewhere: %s))"%(name, msg)

def formatDisconnect(tree):
    return "Disconnected: %s (%s)"%(tree.xpathEval("//Reason")[0].content,
                                    tree.xpathEval("//Message")[0].content)

def formatMessageBox(tree):
    return "]] %s: %s"%(tree.xpathEval("//Severity")[0].content,
                        tree.xpathEval("//Message")[0].content)

def formatGroupMessage(tree):
    return "(Group message) %s: %s"%(tree.xpathEval("//Name")[0].content,
                                     tree.xpathEval("//Message")[0].content)

def formatGroupNotice(tree):
    return "((Group Notice)): (%s) %s: %s"%(tree.xpathEval("//Name")[0].content,
                                            tree.xpathEval("//Subject")[0].content,
                                            tree.xpathEval("//Message")[0].content)

def formatLocation(tree):
    return "Location: %s (%s, %s, %s)"%(tree.xpathEval("//SimName")[0].content,
                                        tree.xpathEval("//X")[0].content,
                                        tree.xpathEval("//Y")[0].content,
                                        tree.xpathEval("//Z")[0].content)

def formatParcel(tree):
    return "Parcel: %s"%tree.xpathEval("//Name")[0].content

def formatDefault(tree):
    return tree.__str__()

def Quit(*args):
    import sys
    print "Exitting, right??"
    os.kill(os.getpid(),1)
    sys.exit(0)

def presentResponse(s):
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
            (lambda tree: "<<"+tree.xpathEval("//Name")[0].content + " is " + \
                 tree.xpathEval("//Status")[0].content+">>"),
        'Chat': formatChat,
        'Error':
            (lambda tree: "!!Error: %s!!"%tree.xpathEval("//Error")[0].content),
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
        'Ping': (lambda x: ''),
        }
    todo=handlers.get(resptype,formatDefault)
    msg=None
    try:
        msg=todo(tree)
    except:
        print "!Exception!: "+s
    if msg:
        print '==\n%s\n=='%msg
        
if __name__ == '__main__':
    # import re
    tn=Telnet('localhost', port)
    thread=threading.Thread(target=keepReading, args=(tn,))
    thread.start()
    while True:
        if thread and not thread.isAlive():
            thread=threading.Thread(target=keepReading, args=(tn,))
            thread.start()
        line=sys.stdin.readline().strip()
        args=line.split(" ")
        cmd=args[0]
        outmsg=None
        if cmd == 'Login':
            outmsg=loginmsg(*args[1:])
        elif cmd == 'Logout':
            outmsg=logoutmsg
        elif cmd == 'Friends':
            outmsg = friendslistmsg
        elif cmd == 'Say':
            outmsg = chatSend(line.split(' ',1)[1])
        elif cmd == '888Say':
            outmsg = chatSend(line.split(' ',1)[1], 888)
        elif cmd == 'IM':
            outmsg = instantMessage(args[1],
                                    line.split(' ',2)[2])
        elif cmd == 'Home':
            outmsg=gohomemsg
        elif cmd == 'Pong':
            outmsg=pongmsg
        elif cmd == 'Location':
            outmsg=currentLocationmsg
        elif cmd in ['Quit', 'Exit']:
            Quit()
        else:
            print "??"
            outmsg=cmd          # Escape clause to type whatever we want.
        if outmsg:
            outmsg=outmsg.encode('utf-8')
            print "\t"+outmsg
            tn.write(outmsg+"\n")
            print "\n"
        print "---\n"

