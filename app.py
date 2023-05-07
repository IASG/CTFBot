__author__ = "IASG Cabinet - (Trent Walraven [trwbox])"
__copyright__ = "Copyright (C) 2023 IASG"
__version__ = "0.0.1-alpha"

# First import the dotenv module and load the .env file
# This needs to be done before other imports
from dotenv import load_dotenv
load_dotenv()
import asyncio
import discord
import io
import os
import pytz
import requests
import time
from typing import Union
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Get the token from the environment variables
TOKEN = os.getenv('TOKEN')
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST")
# Create the MongoDB client
url = f"mongodb+srv://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}/?retryWrites=true&w=majority"
client = MongoClient(url, server_api=ServerApi('1'))
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
# If the DB connection fails, print the error and exit since it is required
except Exception as e:
    print(e)
    exit()
# Get the correct database and collection to use for the bot
db = client.get_database("ctf_passwords")
collection = db.get_collection("passwords")

# The general URL for the CTFTime API
GENERAL_URL = "https://ctftime.org/api/v1/events/?limit={}&start={}&finish={}"
# The URL for a specific CTF
EVENT_URL = "https://ctftime.org/api/v1/events/{}/"
# The user agent for the bot
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
# The maximum number of CTFs to get from the API
CTF_LIMIT = 100
# The description of the bot for the help command
DESCRIPTION = '''A bot that is part of the IASG Discord server'''
# The prefix for the bot
COMMAND_PREFIX = '//'
# The number of days to keep a username and password in the database after the CTF is over
DAYS_TO_KEEP = 7

# The intents for the bot
intents = discord.Intents.default()
# The bot needs to be able to get members and message content along with the default intents
intents.members = True
intents.message_content = True

# Create the bot itself
bot = commands.Bot(command_prefix=COMMAND_PREFIX, description=DESCRIPTION, intents=intents)

def get_times(days: int = 7) -> tuple:
    """Takes a number of days and returns the current unix timestamp and the future unix
    timestamp based on the number of days
    
    Args:
        days (int, optional): The number of days to add to the current time. Defaults to 7.
        
    Returns:
        tuple: A tuple containing the current unix timestamp and the future unix timestamp
        (current, future)
    """
    current = round(time.time())
    # Add 7 days to current time
    future = round(current + (days * 86400))
    return (current, future)

def convert_timestamps(start: str, finish: str) -> dict:
    """Converts the start and finish times to strings and timestamps
    
    Args:
        start (str): The start time in ISO format
        finish (str): The finish time in ISO format
    
    Returns:
        dict: A dict containing the start and finish times as strings in Central Time 
        and unix timestamps. Along with including prior timestamps to get the current CTFs
        TODO: Add the code for the prior times to get current CTFs, it can probably be defaulted to 7 days?
        Example:
        {
            "prior_string": "Central Time String",
            "prior_timestamp": unix_timestamp,
            "start_string": "Central Time String",
            "start_timestamp": unix_timestamp,
            "finish_string": "Central Time String",
            "finish_timestamp": unix_timestamp
        }
    """
    start_time = datetime.fromisoformat(start)
    finish_time = datetime.fromisoformat(finish)
    start_string = start_time.astimezone(pytz.timezone('US/Central')).strftime("%d %b %Y %I:%S %p %Z")
    start_timestamp = round(start_time.timestamp())
    finish_string = finish_time.astimezone(pytz.timezone('US/Central')).strftime("%d %b %Y %I:%S %p %Z")
    finish_timestamp = round(finish_time.timestamp())
    return {
        "start_string": start_string,
        "start_timestamp": start_timestamp,
        "finish_string": finish_string,
        "finish_timestamp": finish_timestamp
    }

@bot.event
async def on_ready():
    """The function that runs when the bot is ready to be used. It will print the
    bot's name and ID to the console. It will also start any of the needed tasks
    that are not already running.
    """
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    # This will start the clean_db function, if it is not already running
    if not clean_db.is_running():
        clean_db.start()

@bot.command("ctf")
async def ctf(ctx, days: Union[int, str] = 7, *args):
    """Gets up to 100 CTFs in the specified number of days. Default is 7. W
    This will skip onsite CTFs by default, but this can be changed by setting
    This will also skip non Open CTFs by default.
    
    Args:
        ctx (discord.ext.commands.Context): The context of the command
        days (Union[int, str], optional): The number of days to get CTFs for. Defaults to 7.
            Needs to be an integer, but the Union allows for a string to be passed in, and
            an error will be sent if it is not an integer.
        *args: Any extra arguments that are passed in. These are not used, but will prevent
            the bot from throwing an error if the user passes in extra arguments.
    Returns:
        None: Returns nothing
    """
    # A variable that can be set if you want ot skip onsite CTFs
    # Default to hardcoding right now, but might make it an option later?
    skip_onsite = True
    # A variable that can be set if you want to skip non Open CTFs
    # Default to hardcoding right now, but might make it an option later?
    skip_non_open = True

    # Don't respond to bots to prevent infinite loops
    if ctx.author.bot:
        return

    # Check if the days is an integer
    if type(days) != int:
        # Send a message to the user telling them that the days needs to be an integer
        # The message will be deleted after 5 seconds
        await ctx.send(f"Days must be an integer\nUsage: `{COMMAND_PREFIX}ctf <days_int>`", delete_after=5)
        # Wait 5 seconds then delete the command message alongside the bot's message
        await asyncio.sleep(5)
        # Delete the command message
        await ctx.message.delete()
        # Return to prevent the bot from continuing
        return
    # Check if the days is less than or equal to 30
    if days > 30:
        # Send a message to the user telling them that the days needs to be less than or equal to 30
        # The message will be deleted after 5 seconds
        await ctx.send("Please specify a number of days less than or equal to 30", delete_after=5)
        # Wait 5 seconds then delete the command message alongside the bot's message
        await asyncio.sleep(5)
        # Delete the command message
        await ctx.message.delete()
        return
    # TODO: To get the current CTFs from the API it looks like it might require setting the start time back X days, 
    #   getting the ctfs, then parsing the finish data to see if it has passed. Then only adding the ones that have not
    #   you could then also compute the hours and days left in the ctf and add that to the embed?
    # Get the current and future timestamps
    current, future = get_times(days=days)
    # Print the URL for debugging
    print(GENERAL_URL.format(CTF_LIMIT, current, future))
    # Get the response from the API
    response = requests.get(GENERAL_URL.format(CTF_LIMIT, current, future), headers=HEADERS)
    # Convert to JSON
    if response.status_code != 200:
        # Send a message to the user telling them that there was an error
        await ctx.send("Error CTFTime API returned: {}".format(response.status_code))
        # Return to prevent the bot from continuing
        return
    # Convert to JSON
    data = response.json()
    # If there is no data, there are no CTFs in the next 7 days
    if len(data) == 0:
        await ctx.send("No CTFs found in the next {} days".format(days))
        return
    # Create temp variables outside the loop
    output = ""
    file = None
    # For all of the CTFs in the response
    for i in data:
        # If the CTF is not open, skip it
        if skip_non_open and i.get("restrictions") != "Open":
            continue
        # If the CTF is onsite, skip it
        if skip_onsite and i.get("onsite") != False:
            continue
        # Get the logo URL
        logo_url = i.get("logo")
        # If there is a logo URL
        if logo_url is not None and logo_url != "":
            # Attempt to get the logo data
            logo_data = requests.get(logo_url, headers=HEADERS)
            # If the status code is 200, the logo was found
            if logo_data.status_code == 200:
                # Create a file object from the logo data
                file = io.BytesIO(logo_data.content)
            else:
                # If the status code is not 200, the logo was not found
                # Set the file to None
                file = None
        else:
            # If there is no logo, set the file to None
            file = None
        # Create a new embed message
        embed = discord.Embed()
        # If there is a file, and the logo data status code is 200
        if file != None and logo_data.status_code == 200:
            # Add the file to the embed
            test = discord.File(file, filename="logo.png")
            # Set the thumbnail to the file
            embed.set_thumbnail(url="attachment://logo.png")
        # Add the fields to the embed, some fields are used more than once
        # so they are stored in variables
        # The ID of the CTF
        ctf_id = i.get("id")
        # From the database, get all the documents with the ctf_id
        team_data = collection.find({"ctf_id": ctf_id})
        team_creds = []
        # If there were documents found
        if team_data is not None:
            # Iterate over all the team data
            while team_data.alive:
                try:
                    # Get the next document, this can trigger a StopIteration error
                    data = team_data.next()
                    # Add the credentials to the list
                    team_creds.append(data.get("credentials"))
                except StopIteration:
                    break
        # If there were no creds found, set it to None for easier checking later
        if len(team_creds) == 0:
            team_creds = None

        # The start and finish times of the CTF in unix, and central time
        output = convert_timestamps(i.get("start"), i.get("finish"))
        # The duration of the CTF in days and hours
        duration = i.get("duration")
        # The description of the CTF
        description = i.get("description")

        # The name of the CTF
        embed.add_field(name="Name", value=i.get("title"), inline=True)
        # The ID of the CTF
        embed.add_field(name="CTF ID", value=ctf_id, inline=True)
        # The URL of the CTF
        embed.add_field(name="URL", value=i.get("url"), inline=False)
        # The start and finish strings for Central Time Zone
        embed.add_field(name="Start", value=output.get("start_string"), inline=True)
        embed.add_field(name="Finish", value=output.get("finish_string"), inline=True)
        # The format of the CTF
        embed.add_field(name="Format", value=i.get("format"), inline=True)
        # If the durations is not empty
        if duration is not None and duration != "":
            # Create a string for the duration
            duration_string = "Days: " + str(duration.get("days")) + "\nHours: " + str(duration.get("hours"))
            # Add the duration string to the embed
            embed.add_field(name="Duration", value=duration_string, inline=True)
        # If there is team data
        if team_creds is not None:
            # If there are more than 1 set of credentials
            if len(team_creds) > 1:
                # Create empty strings for the team names and passwords
                team_names = ""
                team_passes = ""
                # For all the credentials in the list
                for data in team_creds:
                    # If the team names string is empty, set it to the team name
                    if len(team_names) == 0:
                        team_names = data.get("team_name")
                        team_passes = data.get("team_password")
                    # If the team names string is not empty, add a comma and newline
                    else:
                        team_names = team_names + ",\n" + data.get("team_name")
                        team_passes = team_passes + ",\n" + data.get("team_password")
                # Add the team names and passwords to the embed
                embed.add_field(name="Team Names", value=team_names, inline=True)
                embed.add_field(name="Team Passwords", value=team_passes, inline=True)
            # If there is only 1 set of credentials
            elif len(team_creds) == 1:
                # Add the team name and password to the embed
                embed.add_field(name="Team Name", value=team_creds[0].get("team_name"), inline=True)
                embed.add_field(name="Team Password", value=team_creds[0].get("team_password"), inline=True)
        # If there are no credentials
        else:
            # If there is no team data, add None to the fields
            embed.add_field(name="Team Name", value="None", inline=True)
            embed.add_field(name="Team Password", value="None", inline=True)

        # If there is a description
        if description is not None and description != "":
            # If the description is longer than 1024 characters, truncate it
            if len(description) > 1024:
                description = description[:1024]
            # Add the description to the embed
            embed.add_field(name="Description", value=description, inline=False)
        
        # If a logo was found, send the file with the embed
        if file != None and logo_data.status_code == 200:
            await ctx.send(file=test, embed=embed)
        # If no logo was found, send the embed without the file
        else:
            await ctx.send(embed=embed)

# Get info on a specific CTF
@bot.command("ctf_info")
async def ctf_info(ctx, id: Union[str, int] = None, *args):
    """Gets information about a specific CTF, if a specific CTF ID is given, will always
    succeed. If given a string, it will search for the string in the CTF names over the 
    next 14 days, and return the first one.
    
    Args:
        ctx (discord.ext.commands.Context): The context of the command
        id (Union[str, int], optional): The data the user provides to search for a CTF. 
            Can be a string to search for a name, or an id for a specific CTF. Defaults to None.
        *args: Any extra arguments that are passed in. These are not used, but will prevent
            the bot from throwing an error if the user passes in extra arguments.
    """
    # Don't respond to bots to prevent infinite loops
    if ctx.author.bot:
        return
    # Try to convert the id to an integer, if the auto convert fails
    try:
        id = int(id)
    except ValueError:
        pass
    
    # If the id is still a string, search for CTFs by name
    # TODO: This is a placeholder, it will be implemented later
    if type(id) == str:
        await ctx.send("Searching for CTFs by name", delete_after=10)
        await ctx.send("This function is not currently implemented", delete_after=10)
        return 
    # If the id is an integer, the user is searching for a specific CTF, so get the data
    # from the API for that CTF
    elif type(id) == int:
        # Try to get the data from the database for the CTF ID
        database_data = collection.find({"ctf_id": id})
        team_data = []
        # Go through all the data retrieved from the database
        if database_data is not None:
            # While data still exists
            while database_data.alive:
                # Attempt to get the next document
                try:
                    # Store the data in a variable, this can trigger a StopIteration error if there is no data
                    data = database_data.next()
                    # Add the credentials to the array if it succeeded
                    team_data.append(data.get("credentials"))
                # Otherwise, break out of the loop
                except StopIteration:
                    break
        # If there was no data found, set the team data to None
        if len(team_data) == 0:
            team_data = None
        
        # Create the API URL for the CTF
        api_url = EVENT_URL.format(id)
        # Print the URL for debugging
        print(api_url)
        # Get the response from the API for the url
        response = requests.get(api_url, headers=HEADERS)
        # If the response status code is not 200, send an error message
        if response.status_code != 200:
            await ctx.send("Error: CTFTime API returned status code {}".format(response.status_code), delete_after=10)
            return
        # Get the JSON data from the response if it succeeded
        api_data = response.json()
        # Take the start and finish times from the data and convert them to strings and timestamps
        output = convert_timestamps(api_data.get("start"), api_data.get("finish"))
        # Create an empty embed
        embed = discord.Embed()
        # Set the title of the embed
        embed.title = api_data.get("title")
        # Add a field for the URL
        embed.add_field(name="URL", value=api_data.get("url"), inline=False)
        # Add a field for the CTF ID
        embed.add_field(name="CTF ID", value=id, inline=True)
        # Add the team name and password to the embed
        # If there is team data
        if team_data is not None:
            # If there is only 1 set of credentials
            if team_data == 1:
                embed.add_field(name="Team Name", value=team_data.get("team_name"), inline=True)
                embed.add_field(name="Team Password", value=team_data.get("team_password"), inline=True)
            # If there are more than 1 set of credentials
            else:
                # Take the team names and passwords and put them in a string
                team_name_string = ""
                team_password_string = ""
                for data in team_data:
                    if len(team_name_string) == 0:
                        team_name_string = data.get("team_name")
                        team_password_string = data.get("team_password")
                    else:
                        # Commas and newlines are added to make it easier to read
                        team_name_string = team_name_string + ",\n" + data.get("team_name")
                        team_password_string = team_password_string + ",\n" + data.get("team_password")
                # Add the team names and passwords to the embed
                embed.add_field(name="Team Names", value=team_name_string, inline=True)
                embed.add_field(name="Team Passwords", value=team_password_string, inline=True)
        # If there is no team data in the database
        else:
            # Add None to the fields
            embed.add_field(name="Team Name", value="None", inline=True)
            embed.add_field(name="Team Password", value="None", inline=True)
        # Add a field for the start and finish times
        embed.add_field(name="Start", value=output.get("start_string"), inline=True)
        embed.add_field(name="Finish", value=output.get("finish_string"), inline=True)
        # Add a field for the format
        embed.add_field(name="Format", value=api_data.get("format"), inline=True)
        # Get the logo URL
        logo_url = api_data.get("logo")
        # If there is a logo URL
        if logo_url is not None and logo_url != "":
            # Attempt to get the logo data
            logo_data = requests.get(logo_url, headers=HEADERS)
            # If the status code is 200, the logo was found
            if logo_data.status_code == 200:
                # Create a file object from the logo data
                file = io.BytesIO(logo_data.content)
                # Add the file to the embed
                test = discord.File(file, filename="logo.png")
                # Set the thumbnail to the file
                embed.set_thumbnail(url="attachment://logo.png")
        # If there is no logo, set the file to None
        else:
            file = None
        # If there is a description
        if api_data.get("description") is not None and api_data.get("description") != "":
            # If the description is longer than 1024 characters, truncate it
            if len(api_data.get("description")) > 1024:
                description = api_data.get("description")[:1024]
            # Add the description to the embed
            embed.add_field(name="Description", value=api_data.get("description"), inline=False)
        # If a logo was found, send the file with the embed
        if file != None and logo_data.status_code == 200:
            await ctx.send(file=test, embed=embed)
        # If no logo was found, send the embed without the file
        else:
            await ctx.send(embed=embed)
        return
    #  If it is not a string or integer, send an error message
    else:
        # Send an error message that will be deleted after 10 seconds
        await ctx.send("Error: ID must be a string or integer", delete_after=10)
        await asyncio.sleep(10)
        # Delete the command message
        await ctx.message.delete()
        # Return to prevent further execution
        return

@bot.command("ctf_pass")
async def ctfPass(ctx, id: Union[int, str] = None, team_name: str = None, team_password: str = None, overwrite: Union[bool, str] = False,  *args):
    """A method for setting the team name and password for a CTF. This will check the database
    for the CTF ID, and a team name. If the team name already exists, it will send an error message
    unless the overwrite flag is set to true. If the overwrite flag is set to true, it will delete
    the existing document from the database and create a new one with the new credentials. If passed
    only a CTF ID, it will run the ctf_info command with the given ID instead.

    Args:
        ctx (discord.ext.commands.Context): The context of the command
        id (Union[int, str], required): The CTF ID to set the credentials for. Defaults to None.
        team_name (str, required): The team name to set. Defaults to None.
        team_password (str, required): The team password to set. Defaults to None.
        overwrite (Union[bool, str], optional): A flag to overwrite existing credentials. Defaults to False.
        *args: Any extra arguments that are passed in. These are not used, but will prevent
            the bot from throwing an error if the user passes in extra arguments.
    """
    overwrote = False
    # If there is just a CTF ID, then get the team name and password from the database
    # This does not require cabinet permissions
    if id is not None and team_name is None and team_password is None:
        # Try to convert the id to an integer, if the auto convert fails
        try:
            id = int(id)
        except ValueError:
            ctx.send("Error: ID must be an integer", delete_after=10)
            await asyncio.sleep(10)
            await ctx.message.delete()
            return
        # If the number is an integer, we can just run the ctf_info command
        await ctf_info(ctx, id)
        return
    # If there is more than just an id provided, check for required fields
    elif id is None or team_name is None or team_password is None:
        # If any of the required fields are not provided, send an error message
        # that will be deleted after 10 seconds
        await ctx.send(f"Error: Required field not provided\nCommand Usage: `{COMMAND_PREFIX}ctf_pass <ctf_id_int> <team_name_str> <team_password_str> [overwrite_bool Optional]`", delete_after=10)
        # Wait 10 seconds
        await asyncio.sleep(10)
        # Delete the command message
        await ctx.message.delete()
        # Return to prevent further execution
        return
    # Check for correct types on all the fields
    elif type(id) != int or type(team_name) != str or type(team_password) != str or type(overwrite) != bool:
        # Send an error message about required types that will be deleted after 10 seconds
        await ctx.send(f"Error: Required field has incorrect type\nCommand Usage: `{COMMAND_PREFIX}ctf_pass <ctf_id_int> <team_name_str> <team_password_str> [overwrite_bool Optional]`", delete_after=10)
        # Wait 10 seconds
        await asyncio.sleep(10)
        # Delete the command message
        await ctx.message.delete()
        # Return to prevent further execution
        return
    # Check that the user has the role "Cabinet" to prevent abuse
    elif not any(role.name == "Cabinet" for role in ctx.author.roles):
        # TODO: Make this instead create a 
        # Send an error message
        await ctx.send("Error: You do not have permission to use this command, please request a cabinet member add the credentials")
        # Return to prevent further execution
        return

    # Try to get the data for the ctf_id from the database
    # This will get every document with the ctf_id, so there could be multiple
    mongo_data = collection.find({"ctf_id": id})
    # An array to store all the credentials for the CTF
    current_creds = []
    # If there was data found
    if mongo_data is not None:
        # Iterate over all the data
        while mongo_data.alive:
            # Try to get the next document from the query
            try:
                # Store that data in a variable, this can trigger a StopIteration error
                data = mongo_data.next()
                # Add the mongo document to the array
                current_creds.append(data)
            except StopIteration:
                break
    
    # This could probably be done with a query
    # TODO: Make this a query instead of iterating over all the data

    # If there were creds parsed from the database
    if len(current_creds) > 0:
        # For all the documents in the array
        for creds in current_creds:
            # Get the credentials dictionary from the document
            temp = creds.get("credentials")
            # If the team name given is the same as a name that already exists, and overwrite is false
            if temp.get("team_name") == team_name and not overwrite:
                # Send an error message that will be deleted after 10 seconds
                await ctx.send("Error: Team name \"{}\" already exists for CTF ID {}".format(team_name, id), delete_after=10)
                await ctx.send("Use the overwrite flag to overwrite the existing team password", delete_after=10)
                # Wait 10 seconds
                await asyncio.sleep(10)
                # Delete the command message
                await ctx.message.delete()
                # Return to prevent further execution
                return
            # If overwrite is true, delete the existing document from the database
            elif temp.get("team_name") == team_name and overwrite:
                # Delete by the _id of the document since it is unique
                collection.delete_one({"_id": creds.get("_id")})
                # Set overwrote to true so the bot can send a different message
                overwrote = True
                break
    
    # Get the CTF data from ctftime
    # Print the URL for debugging
    print(EVENT_URL.format(id))
    response = requests.get(EVENT_URL.format(id), headers=HEADERS)
    # If the response status code is not 200, send an error message
    if response.status_code != 200:
        # Send an error about the api response
        await ctx.send("Error: CTFTime API returned status code {}".format(response.status_code))
        # Return to prevent further execution
        return
    # Get the JSON data from the response if it succeeded
    data = response.json()
    # If the data is empty, 
    if len(data) == 0:
        # Send an error message that the CTF ID was not found if the data is empty
        await ctx.send("CTF ID not found on CTFTime API")
        # Return to prevent further execution
        return

    # Get the start and finish timestamps from the data
    output = convert_timestamps(data.get("start"), data.get("finish"))
    # Create an empty dict for the database data
    database_data = {}
    # In the credentials section, create another dict for the team name and password
    database_data["credentials"] = {}
    # Add the team name and password to the credentials dict
    database_data["credentials"]["team_name"] = team_name
    database_data["credentials"]["team_password"] = team_password
    # Add the name, and url to 
    database_data["title"] = data.get("title")
    # Add the ctf_id to the database data
    database_data["ctf_id"] = id
    # Add the unix timestamps to the database data, for cleaning up the database
    # later
    database_data["start"] = output.get("start_timestamp")
    database_data["finish"] = output.get("finish_timestamp")
    
    # Add the database data to the database
    # Insert the data into the database
    collection.insert_one(database_data)
    # Send a success message
    embed = discord.Embed()
    # Set the title of the embed
    embed.title = "CTF Password Added"
    # If the team was overwritten, send a different message
    if overwrote:
        embed.description = "CTF team {} already existed in the database, overwriting".format(team_name)
    # Attempt to get the CTFs logo
    logo_url = data.get("logo")
    file = None
    # If there is a logo URL
    if logo_url is not None and logo_url != "":
        # Attempt to get the logo data
        logo_data = requests.get(logo_url, headers=HEADERS)
        # If the status code is 200, the logo was found
        if logo_data.status_code == 200:
            # Create a file object from the logo data
            file = io.BytesIO(logo_data.content)
        # If the status code is not 200, the logo was not found
        else:
            # Set the file to None
            file = None
    # If there is no url, set the file to None
    else:
        file = None
    # If there is a file, and the logo data status code is 200
    if file != None and logo_data.status_code == 200:
        # Add the file to the embed
        test = discord.File(file, filename="logo.png")
        # Set the thumbnail to the file
        embed.set_thumbnail(url="attachment://logo.png")
    # Add the CTF Name field
    embed.add_field(name="CTF Name", value=data.get("title"), inline=False)
    # Add the CTF ID field
    embed.add_field(name="CTF ID", value=id, inline=False)
    # Add the Team Name field
    embed.add_field(name="Team Name", value=team_name, inline=False)
    # Add the Team Password field
    embed.add_field(name="Team Password", value=team_password, inline=False)
    # If a logo was found, send the file with the embed
    if file != None and logo_data.status_code == 200:
        await ctx.send(file=test, embed=embed)
    # If no logo was found, send the embed without the file
    else:
        await ctx.send(embed=embed)

@bot.command('testing')
async def testing(ctx, *args):
    """Testing command that states if the user is in the Cabinet role or not"""
    print(ctx.channel.id)
    if ctx.author.bot:
        return
    #cabinet = discord.role(998336323154878524, 'Cabinet')
    for i in ctx.author.roles:
        if i.name == "Cabinet":
            await ctx.send("User is in Cabinet")
    await ctx.send("Testing")
    args = ', '.join(args)
    await ctx.send(args)

@tasks.loop(hours=24)
async def clean_db():
    """Cleans the database of extra data to save space. It will remove all data
    for CTFs that have finished more than 7 days ago. This will loop every
    24 hours.
    """
    print("Cleaning database")
    removed = 0
    # Get all the data from the database where the finish timestamp is less than
    # the current time + the number of days to keep
    all_data = collection.find({"finish": {"$lt": time.time() - DAYS_TO_KEEP * 86400}})
    for i in all_data:
        collection.delete_one({"_id": i.get("_id")})
        removed = removed + 1
    # Get the number of documents removed
    print("Removed {} documents".format(removed))

@bot.command('force_clean_db')
async def force_clean_db(ctx):
    """Forces the database to be cleaned just like the clean_db function. This
    will remove all data for CTFs that have finished more than 7 days ago.
    """
    print("Cleaning database")
    # Get all the data from the database where the finish timestamp is less than
    # the current time + the number of days to keep
    all_data = collection.delete_many({"finish": {"$lt": time.time() - DAYS_TO_KEEP * 86400}})
    # Get the number of documents removed
    removed = all_data.deleted_count
    print("Removed {} documents".format(removed))
    await ctx.send("Removed {} documents".format(removed))

# Start the bot with the token
bot.run(token=TOKEN)