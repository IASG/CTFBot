# IASG CTFBot

This is a bot that will be run in the IASG discord server to help with maintaining CTFs. The bot is currently running on [botshard.com](https://botshard.com) with a MongoDB from [cloud.mongodb.com](https://cloud.mongodb.com). Both on the free tier, of a personal account. This is using the [discord.py](https://discordpy.readthedocs.io/en/stable/index.html#) for the discord bot, and [pymongo](https://pymongo.readthedocs.io/en/stable/) for the MongoDB connection.

## Deployment

Currently, the bot is deployed on [botshard.com](https://botshard.com) with a MongoDB from [cloud.mongodb.com](https://cloud.mongodb.com). Both on the free tier, of a personal account. Right now, code is being manually added to botshard, along with a manual addition of `.env` for secrets, and a manual restart of the bot. The secrets shouldn't be changing often, and the automatic update and restart of the bot on new code push would be nice though.

## Database info

The database is a MongoDB with a database of `ctf_passwords` and a collection of `passwords`. The `passwords` collection has the following schema:

```js
{
    "_id": "ObjectId", // This is assigned by MongoDB
    "title": "ctfname",
    "ctf_id": "ctftime_id_int",
    "start": "unix_timestamp_int",
    "finish": "unix_timestamp_int",
    "credentials": {
        "team_username": "team_name",
        "team_password": "team_password"
    }
}
```

TODO: A lot. A rough list in no particular order:

- [ ] Get the currently ongoing CTFs from CTFTIme instead of the just the future one.
- [ ] Ping the @CTF role with the creds for a CTF when a CTF with creds starts
- [ ] Generally more logging for the bot as a whole
- [ ] If the CTFTime API fails retry at least once instead of just sending an error message
- [ ] Test long term MongoDB, to see if the host name changes
  - [ ] If it does, figure out how to automatically update the bot
- [ ] Automate sending of new CTF details to a channel
  - [ ] Likely bots in ctf category
  - [ ] Suggested time is weekly on Thursday
  - Should be doable with a loop similar to `clean_db`, but instead with exact times?
    - [loop docs with exact times](https://discordpy.readthedocs.io/en/stable/ext/tasks/index.html?highlight=tasks#discord.ext.tasks.Loop.time)
- [ ] Documentation in the code with comments
- [ ] Get account on botshard and mongodb for IASG
  - [ ] Get a github account? To allow botshard to pull from a private github repo?
- [ ] Add a command to request CTF credentials
  - [ ] Add a command to request CTF credentials by name
  - [ ] Add a command to request CTF credentials by CTF_ID
- [ ] Generic CTF searching
- [ ] Permissions checking for adding CTF credentials
  - [ ] Allow non-cabinet to request adding CTF credentials, with approval from reaction of cabinet member?
- [ ] Rate limiting for requesting CTF data
- [X] Automatic clearing of CTF credentials after CTF is over
  - [ ] Make the bot log how much it has deleted
  - Clears credentials after 1 week of CTF being over
- [ ] Verify that the embeds work properly with accessability settings on
- [ ] After a significant number of features are completed, permissions on the main github repo
- [ ] Lock dependencies to specific versions to prevent breaking changes from dependencies

## Running the bot

To run the bot, you need to have a `.env` file in the root directory of the project. This file should contain the following:

```env
TOKEN=discord_bot_token
MONGO_USER=mongodb_username
MONGO_PASSWORD=mongodb_password
MONGO_HOST=mongodb_host_url
```

This can optionally be run in a python virtual environment. To do this, run the following:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

If you choose not to use a virtual environment, you can just run

```bash
pip3 install -r requirements.txt
python3 app.py
```
