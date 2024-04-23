# -*- coding: utf-8 -*-
"""
@author: Massieh
"""

#pip install spotipy
#pip install discord.py
#pip install pynacl
#pip install yt_dlp
#You must install FFMPEG to use any audio related feature 

#imports
import spotipy
import random
import discord
import asyncio
import sys
import yt_dlp 
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials

#Tokens
DISCORD_TOKEN=None
SPOTIFY_CLIENT_ID=None
SPOTIFY_CLIENT_SECRET=None

#Check if tokens were properly modified
if DISCORD_TOKEN is None or SPOTIFY_CLIENT_ID is None or  SPOTIFY_CLIENT_ID is None :
    sys.exit("Veuillez mettre à jour les tokkens puis redémarrer l'application")

#variables
SPOTIFY_CREDENTIALS= SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID,client_secret=SPOTIFY_CLIENT_SECRET)
sp=spotipy.Spotify(client_credentials_manager=SPOTIFY_CREDENTIALS)
Volume=1
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states= True
bot = commands.Bot(command_prefix='?',intents=intents, help_command=None) #We set the help_command as None so that we can create a brand new one




#any function used for the command play :

#if there were no player given or the bot isn't in a voice channel the game doesn't start    
async def Check_Conditions(ctx,joueurs):
    if len(joueurs)==0 :
        await ctx.send("Il faut mentionner au moins 1 joueur")
        return True    
    if not ctx.voice_client:
        await ctx.send("Je ne suis pas dans un vocal (je peux en rejoindre un avec ?join)")
        return True
    return False

#getting a playlist from every player, extracting every song appearing at least once in a global playlist and setting up a dictionary to store member scores
async def setup_game(ctx,joueurs): 
    scores = {}
    playlists=[]
    playlist_global=[]
    for joueur in joueurs :
        await ctx.send(joueur.mention+", donne moi l'id de ta playlist") 
        try:
            id_playlist_joueur = await bot.wait_for('message', check=lambda message: message.author==joueur,timeout=45) 
        except asyncio.TimeoutError:
            await ctx.send("Trop de temps à répondre annulation de la partie")
            return 
        scores[joueur] = 0
        playlist= await recup_playlist(ctx,str(id_playlist_joueur.content))
        playlists.append(playlist)
        playlist_global.extend(playlist)      
    playlist_global=retire_double(playlist_global)    
    await ctx.send("J'ai recensé "+str(len(playlist_global))+" sons différents parmi toutes les playlists")
    return scores,playlists,playlist_global

#asks for a number of turns until it's a valid answer or timeout
async def get_turn(ctx,joueurs,nbr_titre):
    nbr_tour=-1
    await ctx.send(f"{joueurs[0].mention} à vous de choisir, combien de manches ? (Au moins 1, au plus {nbr_titre})")
    while (nbr_tour==-1): 
        try:
            requete_nbr_tour = await bot.wait_for('message', check=lambda message: message.author==joueurs[0],timeout=45)
            requete_nbr_tour= requete_nbr_tour.content
            if (requete_nbr_tour.isdigit() and  (nbr_titre+1) > int(requete_nbr_tour) > 0 ):
                nbr_tour=int(requete_nbr_tour)
            else:
                await ctx.send("Le format du nombre donné n'est pas adapté ou le nombre de tour proposé n'est pas bon")
        except asyncio.TimeoutError:
            await ctx.send("Trop de temps à répondre annulation de la partie")
            return
    
#Gets a playlist from an ID    
async def recup_playlist(ctx,id_playlist):
    try:
        playlist=sp.playlist_tracks(id_playlist)
    except: #checks if ID is valid
        await ctx.send("Une erreur s'est produite, veuillez revérifier l'ID fourni. Si l'ID est bon vérifiez le tokken. Annulation de la partie.")
        return
    titres=[]
    message= await ctx.send("je n'ai récupéré aucun son dans la playlist pour l'instant")
    compteur_playlist=100
    compteur_rat=0
    while True: #Spotify's API allows to grab only up to 100 songs at a time, this loop is a workaround 
        sous_playlist=playlist["items"]        
        for titre in sous_playlist :
            if titre["track"] and titre["track"]["preview_url"]:
                titres.append(titre["track"])
            else:
                compteur_rat+=1
        if not playlist["next"]:
            break
        await message.edit(content=(f"j'ai récupéré les {len(titres)}+ premiers sons de la playlist"))
        playlist=sp.playlist_tracks(id_playlist,offset=compteur_playlist)
        compteur_playlist+=100
    if (compteur_rat==0):
        await message.edit(content=("j'ai récupéré les {len(titres)} sons de la playlist"))
    else:
        await message.edit(content=(f"j'ai récupéré {len(titres)} sons de la playlist, {compteur_rat} n'ont pas pu être récupérées"))
    return titres

async def update_score(ctx,son,playlists,scores,messages_id):
    Positifs=dans_playlist(son, playlists) #checks if it was in the playlist of the given player
    joueur=0
    for message_id in messages_id:
        message=await ctx.channel.fetch_message(message_id) #it's mandatory to fetch messages instead of storing them, otherwise the reactions won't update themselves 
        reaction = discord.utils.get(message.reactions, emoji="✅")
        if reaction:
            async for user in reaction.users():
                if not user.bot:
                    if user not in scores: #creates a score in case an outsider wants to join the game
                        scores[user] = 0
                    if joueur in Positifs: #if it's in the playlist of the given player increment the score, decrement otherwise
                        scores[user]+=1
                    else: 
                        scores[user]-=1
        joueur+=1
    return scores      

async def afficher_score(ctx,scores):
    s="Recapitulation des scores :"
    for joueur in scores:
        s+=f"\n{joueur.display_name} : {scores[joueur]}"
    await ctx.send(s)
    return
                    
async def music_game(ctx,joueurs,tour,son):
    global Volume
    vocal=ctx.voice_client
    messages=[]
    await ctx.send(f"tour {tour} : Le son qui se joue actuellement est "+son["name"])
    for joueur in joueurs:
        message = await ctx.send(f"Est-il dans la playlist de {joueur.display_name} ?")
        await message.add_reaction("✅")
        messages.append(message.id)
    vocal.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(executable="ffmpeg", source=str(son["preview_url"]))))
    vocal.source.volume=Volume
    await asyncio.sleep(30) #a preview lasts exactly 30 sec and we want to play it fully to give time to the players to react to the emojis
    return messages

#Checks who has this song in their playlist
def dans_playlist(nom_son,playlists):
    res=[]
    for i in range (len(playlists)):
        if nom_son in playlists[i] :
            res.append(i)
    return res

#Removes every doubles to even up the odds and avoid having the same song playing twice
def retire_double(playlist):
    playlist_sans_double=[]
    for son in playlist :
        if son not in playlist_sans_double:
            playlist_sans_double.append(son)
    return playlist_sans_double
    

#Events
@bot.event        
async def on_ready():
    print("Le bot fonctionne")

#Commands    
#Makes the bot join a voice channel
@bot.command()
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("Tu n'es pas dans un vocal")        
    else:
        await ctx.message.author.voice.channel.connect()

@bot.command()
#Makes the bot leave the voice channel
async def leave(ctx):
    vocal=ctx.voice_client
    if vocal:
        await vocal.disconnect()
    else:
        await ctx.send("Je ne suis pas dans un vocal")   

@bot.command()
#Sets the volume of every upcoming piece of media played, resets back to 100% when the bot is shut down
async def vol(ctx, x):
    global Volume
    vocal = ctx.voice_client
    
    x=int(x) if x.isdigit() else "blabla"   
    if type(x) is not int :
        await ctx.send("Le volume donné n'est pas dans un format adapté")
        return
    
    if (x<0 or x>100):
        await ctx.send("le volume doit être un entier compris entre 0 et 100")
        return
    
    Volume=x/100
    if vocal and vocal.is_playing():
        vocal.source.volume=Volume
    await ctx.send(f"le volume est réglé à {x}%")
    return

@bot.command()
#Pauses the song currently played
async def pause(ctx):
    vocal=ctx.voice_client
    if not vocal:
        await ctx.send("Je ne suis pas dans un vocal (je peux en rejoindre un avec ?join)")
        return
    if vocal.is_playing():
        vocal.pause()
        await ctx.send("J'ai mis en pause la musique. Tu peux reprendre la lecture en faisant ?pause")
        return
    if vocal.is_paused():
        vocal.resume()
        await ctx.send("J'ai repris la lecture de la musique")
        return
    await ctx.send("Je ne jouais pas de musique")


@bot.command()
#Starts a game of woodis
async def play(ctx,*joueurs:discord.Member):
    #checks if the game is playable
    if (await Check_Conditions(ctx, joueurs)):
        return
    #Gets every playlists and setups the score system    
    scores,playlists,playlist_global=await setup_game(ctx, joueurs)
    #How many turns ?
    nbr_tour=await get_turn(ctx, joueurs, len(playlist_global))
    #Game Part
    for i in range (nbr_tour):
        son=random.choice(tuple(playlist_global))
        messages_id=await music_game(ctx,joueurs,i+1,son)
        scores=await update_score(ctx,son,playlists,scores,messages_id)
        await afficher_score(ctx,scores)
        playlist_global.remove(son)
    await ctx.send("FIN DE LA PARTIE !")
    return

@play.error
async def play_error(ctx,error):
    await ctx.send(error)

@bot.command()
#Plays an audio from YouTube
async def m_play(ctx,url:str):
    global Volume
    vocal = ctx.voice_client
    if not vocal:
        await ctx.send("Je ne suis pas dans un vocal (je peux en rejoindre un avec ?join)")
        return
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    await ctx.send("Je récupère les informations de la chanson")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
       son =ydl.extract_info(url, download=False)
    vocal.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(executable="ffmpeg", source=son["url"])))
    vocal.source.volume = Volume
    return        

@bot.command()
async def help(ctx):
    s="```Liste des commandes :"
    s+="\n?join : Me fait rejoindre un salon vocal"
    s+="\n?leave : me fait quitter un salon vocal"
    s+="\n?vol : Configure le volume sonore, donne moi en paramètre une valeur comprise entre 0 et 100"
    s+="\n?m_play : Joue un fichier audio depuis un lien YouTube"
    s+="\n?pause : Met en pause le fichier audio lu depuis YouTube"
    s+="\n?play : Lance une partie de woodis, mentionnez tous les joueurs inclus dans la partie. Exemple d'une partie pour 3 : ?play @mention1 @mention2 @mention3```"
    await ctx.send(s)
    
    
bot.run(DISCORD_TOKEN)
