import slack
import os
from pathlib import Path
from flask import Flask
from slackeventsapi import SlackEventAdapter
from datetime import datetime
from airtable import airtable


#variables
#desired command to read in message - If this tag is added to a message, it will automatically add a blue tickmark to the message, add an entry to airtable, and track all blue tickmark clicks for the message
tagbot = "must-read"

#airtable table name - This is the table you created
tablename = "Slack_Read_List"


# This `app` represents your existing Flask app
app = Flask(__name__)

# Bind the Events API route to your existing Flask app by passing the server
# instance as the last param, or with `server=app`.
#Blind Slack API webclient and Airtable ID and key - When implementing, using a settings file would be more secure.
slack_events_adapter = SlackEventAdapter("Slack app signing secret", "/slack/events", app)
client = slack.WebClient("Oauth Token")
at = airtable.Airtable('Table ID', 'APIKEY')

BOT_ID = client.api_call("auth.test")['user_id']

#write must-read to airtable when a message event is received
@slack_events_adapter.on('message')
def message(payload):
    #assign values    
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')
    messageid = event.get('ts')
    posttime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    channelname = client.conversations_info(channel=channel_id)["channel"]["name"]    
    members = client.conversations_members(channel=channel_id)["members"]
    
    getuser = client.users_info(user=user_id)
    user = getuser["user"]["profile"]["real_name"]


    #load channel members into array and replace with real names
    memberidlist = []
    membernamelist = []
    entryexists = "no"
    memberstring = ""
    countmembers = 0

    for x in range(len(members)):
        memberidlist.append(members[x])    
    
    for y in range(len(memberidlist)):
        temp = client.users_info(user=memberidlist[y])
        temp2 = temp["user"]["profile"]["real_name"]
        if BOT_ID != temp["user"]["id"]:
            membernamelist.append(temp2.title())
            countmembers = countmembers + 1

    #create member string
    for y2 in range(len(membernamelist)):
        memberstring = memberstring + membernamelist[y2] + '\n'
    
    #Scan airtable records and add new record if it does not exist and if must-read (tagbot) was added to a slack message
    records = at.get(tablename)["records"]
    for z in range(len(records)):
        currentid = records[z]["fields"]["Message ID"]
        if currentid == messageid:
            entryexists = 'yes'
            print('exists')
    if entryexists == 'no':
        if tagbot in text:
            at.create(tablename, {'Message ID': messageid, 'Date Created': posttime, 'Message': text, 'Channel': channelname, 'Posted By': user, 'Last Update': posttime, 'Not Read': memberstring, 'Not Read Count': countmembers, 'Read Count': 0})
            entryexists = 'no'
            client.reactions_add(channel=channel_id,timestamp=messageid,name='ballot_box_with_check')   
    
    return 'HTTP 200 OK'


# Create an event listener for "reaction_added"
@slack_events_adapter.on("reaction_added")
def reaction_added(event_data):
    emoji = event_data["event"]["reaction"]
    userid = event_data["event"]["user"]
    channel = event_data["event"]["item"]["channel"]
    messageid = event_data["event"]["item"]["ts"]
    lastreactiontime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    posttime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    #Get message reaction was added to
    response = client.conversations_history(
        channel=channel,
        inclusive=True,
        oldest=messageid,
        limit=1
    )

    #Get message text
    message = response["messages"][0]["text"]
    
    #Array of all reactions on the message
    reactions = response["messages"][0]["reactions"]
    
    #Array of all members in the channel
    members = client.users_list(channel=channel)

    #Create custom arrays
    readlist = []
    readids = ""
    readstring = ""
    notreadstring = ""
    notreadlist = ""
    readcount = 0
    notreadnumber = 0

    if BOT_ID != userid:

        #Read reactions of users - check for correct reaction
        for x in range(len(reactions)):
            if reactions[x]["name"] == 'ballot_box_with_check': 
                    readids = reactions[x]["users"]

        #print("People Read")    
        
        for y in range(len(readids)): 
            readlist.append(client.users_info(user=readids[y]))
            if readlist[y]["user"]["real_name"] != "Read-Tracker":
                readstring = readstring + readlist[y]["user"]["real_name"].title() + '\n'
                readcount = readcount + 1
        

        #print(readstring)

        records2 = at.get(tablename)["records"]
        for z in range(len(records2)):
            currentid2 = records2[z]["fields"]["Message ID"]
            if currentid2 == messageid:
                recordid = records2[z]["id"]                         
                at.update(tablename,recordid, {'Read List': readstring})
                at.update(tablename,recordid, {'Last Update': posttime})
                at.update(tablename,recordid, {'Read Count': readcount})

        for i in range(len(readlist)):
            temp2 = at.get(tablename,recordid)
            notreadlist = temp2["fields"]["Not Read"]
            notreadlist = notreadlist.replace(readlist[i]["user"]["real_name"].title(),"")
            if notreadlist != "":
                notreadlist = notreadlist.strip()
            at.update(tablename,recordid, {'Not Read': notreadlist})
            if notreadlist != "":
                notreadnumber = len(notreadlist.split('\n'))
                at.update(tablename,recordid, {'Not Read Count': notreadnumber})
            if notreadlist == "":
                at.update(tablename,recordid, {'Not Read Count': 0})

    
if __name__ == "__main__":
    app.run(debug=True)