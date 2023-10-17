from django.template import loader
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist

from time import localtime, strftime

import random
import os
import zipfile

from .models import Bid, Session, Group, Participant, Winner


MAX_BDM_PRIZE = 300


@csrf_exempt 
def manager(request):
    if request.method == "GET":
        return HttpResponse("test")
    elif request.method == "POST":
        participant_id = request.POST.get("id")
        block = request.POST.get("round")
        offer = request.POST.get("offer")
        if offer == "result":
            # getting result of an auction
            participant = Participant.objects.get(participant_id = participant_id)            
            group = Group.objects.get(group_number = participant.group_number)
            try:
                winner = Winner.objects.get(group_number = group.group_number, block = block)
                myoffer = Bid.objects.get(participant_id = participant_id, block = block).bid
                maxoffer = winner.maxoffer
                secondoffer = winner.secondoffer
                condition = "treatment" if participant_id == winner.winner else "control"          
                response = "|".join(map(str, [condition, maxoffer, secondoffer, myoffer]))
            except ObjectDoesNotExist:
                response = ""
            return HttpResponse(response)
        elif offer == "login":
            # login screen
            try:
                currentSession = Session.objects.latest('start')
            except ObjectDoesNotExist:
                return HttpResponse("no_open")
            if currentSession.status == "open":
                try:
                    Participant.objects.get(participant_id = participant_id)
                    return HttpResponse("already_logged")
                except ObjectDoesNotExist:                    
                    currentSession.participants += 1 # does not work for some reason - a workaround is through filtering participants within the session and getting the length
                    currentSession.save()
                    participant = Participant(participant_id = participant_id, group_number = -99, session = currentSession.session_number)
                    participant.save()         
                    return HttpResponse("login_successful")   
            elif currentSession.status == "ongoing":
                try:
                    participant = Participant.objects.get(participant_id = participant_id)
                    if participant.group_number == -99:
                        return HttpResponse("not_grouped")
                    group = Group.objects.get(group_number = participant.group_number)
                    return HttpResponse("_".join(["start", str(group.bdm_one), str(group.bdm_two), group.condition]))
                except ObjectDoesNotExist:
                    return HttpResponse("ongoing")
            elif currentSession.status == "closed":
                try:
                    Participant.objects.get(participant_id = participant_id)
                    return HttpResponse("already_logged")
                except ObjectDoesNotExist:       
                    return HttpResponse("closed")
            else:
                return HttpResponse("no_open")
        elif block == "-99":
            # uploading reward at the end
            participant = Participant.objects.get(participant_id = participant_id)    
            participant.reward = offer
            participant.finished = True
            participant.save()
            return HttpResponse("ok")
        elif "outcome" in offer:
            # outcome of the AFTER version in case of the auction round
            participant = Participant.objects.get(participant_id = participant_id)            
            group = Group.objects.get(group_number = participant.group_number)
            if offer == "outcome":
                # downloading the outcome                
                if participant.block != int(block):
                    participant.block = block
                    participant.save()
                winner = Winner.objects.get(group_number = group.group_number, block = int(block) - 1)                
                finishedParticipants = Participant.objects.filter(group_number = group.group_number, block = int(block))
                all_completed = winner.completed == group.participants or len(finishedParticipants) == group.participants
                response = "_".join(["outcome", str(winner.wins), str(winner.reward), str(winner.charity), str(all_completed)])
                return HttpResponse(response)
            else:
                # uploading the outcome
                _, wins, reward, charity = offer.split("_")                
                winner = Winner.objects.get(group_number = group.group_number, block = block)
                if winner.winner == participant_id:
                    winner.wins = wins
                    winner.reward = reward
                    winner.charity = charity
                winner.completed += 1
                winner.save()
                return HttpResponse("ok")
        elif offer == "continue":            
            try:
                participant = Participant.objects.get(participant_id = participant_id)
                currentSession = Session.objects.latest('start')
            except ObjectDoesNotExist:
                return HttpResponse("no")
            if participant.session == currentSession.session_number and currentSession.status == "ongoing":
                return HttpResponse("continue")
            else:
                return HttpResponse("no")
        else:
            # recording a bid
            participant = Participant.objects.get(participant_id = participant_id) 
            bid = Bid(participant_id = participant_id, block = block, bid = offer, group_number = participant.group_number)
            bid.save()            
            group = Group.objects.get(group_number = participant.group_number)
            group_bids = Bid.objects.filter(block = block, group_number = participant.group_number)
            if len(group_bids) == group.participants:
                determineWinner(participant.group_number, block)
            return HttpResponse("ok")


def determineWinner(group_number, block):
    highest_bidder = []
    maxoffer = 0
    secondoffer = 0
    all_members = Participant.objects.filter(group_number = group_number)
    for p in all_members:
        try:
            b = Bid.objects.get(participant_id = p.participant_id, block = block)
        except ObjectDoesNotExist:
            continue
        bid = b.bid
        if bid > maxoffer:
            secondoffer = maxoffer
            maxoffer = bid                        
            highest_bidder = [b.participant_id]
        elif bid == maxoffer:
            secondoffer = maxoffer
            highest_bidder.append(b.participant_id)
        elif bid > secondoffer:
            secondoffer = bid
    random.shuffle(highest_bidder)
    highest_bidder = highest_bidder[0]
    winner = Winner(group_number = group_number, block = block, winner = highest_bidder, maxoffer = maxoffer, secondoffer = secondoffer)
    winner.save()


def results_path():
    if not os.path.exists("results/"):
        os.mkdir("results/")
        # with(open(".gitignore", mode = "w")) as f:
        #     f.write("*\n!.gitignore")
    return "results/"


@csrf_exempt 
def results(request):  
    uploaded_file = request.FILES["results"]
    with open(results_path() + uploaded_file.name, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
    return HttpResponse("ok")



@login_required(login_url='/admin/login/')
def download(request):
    file_path = results_path()
    files = os.listdir(file_path)
    if ".gitignore" in files:
        files.remove(".gitignore")
    files_to_remove = [x for x in files if x.endswith(".zip")]
    for f in files_to_remove:
        os.remove(os.path.join(file_path, f))
        files.remove(f)
    writeTime = localtime()
    try:
        currentSession = Session.objects.latest('start').session_number
    except ObjectDoesNotExist:
        currentSession = "X"
    zip_filename = "data_Selection1_{}_{}_{}.zip".format(strftime("%y_%m_%d_%H%M%S", writeTime), currentSession, len(files))
    zip_file_path = os.path.join(file_path, zip_filename)
    with zipfile.ZipFile(zip_file_path, "w") as zip_file:
        for file in files:
            file_full_path = os.path.join(file_path, file)
            zip_file.write(file_full_path, file)
    with open(zip_file_path, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/zip")
        response["Content-Disposition"] = "attachment; filename={}".format(zip_filename)
        return response  




@login_required(login_url='/admin/login/')
def openSession(request, response = True):
    try:
        currentSession = Session.objects.latest('start')
    except ObjectDoesNotExist:
        currentSession = None
    if currentSession and currentSession.status == "closed":
        currentSession.status = "open"
    elif currentSession and currentSession.status == "ongoing":
        if response:
            return HttpResponse("Není možné otevřít nové sezení, když je spuštěné jiné sezení")
        else:
            return "Není možné otevřít nové sezení, když je spuštěné jiné sezení"
    else:
        otherSessions = Session.objects.filter(status__in=["open", "ongoing", "closed"])
        for oldSession in otherSessions:
            oldSession.status = "finished"
            oldSession.save()
        currentSession = Session(status = "open")
    currentSession.save()    
    if response:
        return HttpResponse("Sezení {} otevřeno".format(currentSession.session_number))
    else:
        return "Sezení {} otevřeno".format(currentSession.session_number)


@login_required(login_url='/admin/login/')
def closeSession(request, response = True):
    try:
        currentSession = Session.objects.get(status = "open")    
        currentSession.status = "closed"    
        currentSession.save()
        text = "Sezení {} uzavřeno pro přihlašování".format(currentSession.session_number)
    except ObjectDoesNotExist:
        text = "Není otevřeno žádné sezení"
    if response:
        return HttpResponse(text)
    else:
        return text


@login_required(login_url='/admin/login/')
def endSession(request, response = True):
    try:
        currentSession = Session.objects.latest('start')
        if currentSession.status == "finished":
            text = "Poslední sezení bylo již ukončeno"
        else:
            currentSession.status = "finished"    
            currentSession.save()
            text = "Sezení {} ukončeno".format(currentSession.session_number)
    except ObjectDoesNotExist:
        text = "V databázi není žádné sezení"
    if response:
        return HttpResponse(text)
    else:
        return text


@login_required(login_url='/admin/login/')
def startSession(request, response = True):
    try:
        currentSession = Session.objects.latest('start')
        if currentSession.status == "finished" or currentSession.status == "ongoing":
            raise Exception
    except Exception:
        if response:
            return HttpResponse("Není zahájeno žádné sezení")
        else:
            return "Není zahájeno žádné sezení"        
    currentSession.status = "ongoing"
    currentSession.save()
    participants = Participant.objects.filter(session = currentSession.session_number)
    number = len(participants)
    groups = number//4
    assignment = [i for i in range(number)]
    random.shuffle(assignment)    
    num = 0
    for i in range(groups):
        bdm_one = random.randint(1, MAX_BDM_PRIZE)
        bdm_two = random.randint(1, MAX_BDM_PRIZE)
        condition = random.choice(["lowinfo", "highinfo", "lowcontrol", "highcontrol"])
        group = Group(session = currentSession.session_number, participants = 4, bdm_one = bdm_one, bdm_two = bdm_two, condition = condition)
        group.save()
        for j in range(4):
            p = participants[num]
            p.group_number = group.group_number
            p.save()
            num += 1
    if response:
        return HttpResponse("Sezení {} zahájeno s {} participanty".format(currentSession.session_number, num))
    else:
        return "Sezení {} zahájeno s {} participanty".format(currentSession.session_number, num)


def showEntries(objectType):
    entries = objectType.objects.all() # pylint: disable=no-member
    if not entries:
        return None
    else:
        fields = [field.name for field in objectType._meta.get_fields()] # pylint: disable=no-member
        content = "\t".join(fields) + "\n" + "\n".join([str(entry) for entry in entries])
        return content


def downloadData(content, filename):
    response = HttpResponse(content, content_type="text/plain,charset=utf8")
    response['Content-Disposition'] = 'attachment; filename={0}.txt'.format(filename)
    return response


@login_required(login_url='/admin/login/')
def downloadAll(request):
    file_path = results_path()
    files = os.listdir(file_path)
    if ".gitignore" in files:
        files.remove(".gitignore")
    tables = {"Sessions": Session, "Groups": Group, "Winners": Winner, "Participants": Participant, "Bids": Bid}
    for table, objectType in tables.items():        
        content = showEntries(objectType)
        filename = table + ".txt"
        files.append(filename)
        with open(os.path.join(file_path, filename), mode = "w") as f:
            if content:
                f.write(content)
            else:
                f.write("")
    files_to_remove = [x for x in files if x.endswith(".zip")]
    for f in files_to_remove:
        os.remove(os.path.join(file_path, f))
        files.remove(f)
    writeTime = localtime()
    try:
        currentSession = Session.objects.latest('start').session_number
    except ObjectDoesNotExist:
        currentSession = "X"
    zip_filename = "all_data_Selection1_{}_{}_{}.zip".format(strftime("%y_%m_%d_%H%M%S", writeTime), currentSession, len(files) - len(tables))
    zip_file_path = os.path.join(file_path, zip_filename)
    with zipfile.ZipFile(zip_file_path, "w") as zip_file:
        for file in files:
            file_full_path = os.path.join(file_path, file)
            zip_file.write(file_full_path, file)
    for table in tables:
        filename = os.path.join(file_path, table + ".txt")
        if os.path.exists(filename):
            os.remove(filename)
    with open(zip_file_path, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/zip")
        response["Content-Disposition"] = "attachment; filename={}".format(zip_filename)
        return response      


@login_required(login_url='/admin/login/')
def delete(request):
    Session.objects.all().delete() # pylint: disable=no-member
    Group.objects.all().delete() # pylint: disable=no-member
    Winner.objects.all().delete() # pylint: disable=no-member
    Participant.objects.all().delete() # pylint: disable=no-member
    Bid.objects.all().delete() # pylint: disable=no-member
    return HttpResponse("Databáze vyčištěna")


@login_required(login_url='/admin/login/')
def deleteData(request):
    file_path = results_path()
    files = os.listdir(file_path)    
    for f in files:
        if not ".gitignore" in f:            
            os.remove(os.path.join(file_path, f))
    return HttpResponse("Data smazána")


def removeParticipant(participant_id):
    try:
        participant = Participant.objects.get(participant_id = participant_id) 
        if participant.finished:
            return("Participant již sezení ukončil")
        elif participant.finished is None:
            return("Participant již byl přeskočen")
        else:
            participant.finished = None
            participant.save()
        session = Session.objects.get(session_number = participant.session)
        if session.status != "ongoing":
            return("Participant není z aktivního sezení")
        group = Group.objects.get(group_number = participant.group_number)
        group.participants -= 1
        group.save()
        winnings = Winner.objects.filter(group_number = participant.group_number)
        if winnings:
            highest = 0
            for win in winnings:
                if win.block > highest:
                    highest = win.block
            lastWinning = Winner.objects.get(group_number = participant.group_number, block = highest)
            if lastWinning.winner == participant_id and not lastWinning.wins and not lastWinning.reward and not lastWinning.charity:
                lastWinning.wins = -99
                lastWinning.reward = -99
                lastWinning.charity = -99
                lastWinning.save()
        for block in range(4,7):
            group_bids = Bid.objects.filter(block = block, group_number = participant.group_number)
            if len(group_bids) == group.participants:
                for bid in group_bids:
                    if bid.participant_id == participant_id:
                        break
                else:
                    determineWinner(participant.group_number, block)
        return("Participant bude ve studii přeskočen")
    except ObjectDoesNotExist as e:
        return("Participant s daným id nenalezen")



@login_required(login_url='/admin/login/')
def administration(request):
    participants = {}
    status = ""
    if request.method == "POST" and request.POST['answer'].strip():
        answer = request.POST['answer']
        if "otevrit" in answer:
            info = openSession(request, response = False)            
        elif "spustit" in answer:
            info = startSession(request, response = False) 
        elif "uzavrit" in answer:
            info = closeSession(request, response = False) 
        elif "ukoncit" in answer:
            info = endSession(request, response = False) 
        elif "ukazat" in answer or "data" in answer:
            info = "Hotovo"            
            if "vse" in answer and ("data" in answer or "stahnout"):
                return downloadAll(request)
            pattern = {"sezeni": Session, "skupiny": Group, "vyherc": Winner, "participant": Participant, "nabidky": Bid}
            for key in pattern:
                if key in answer:
                    content = showEntries(pattern[key])
                    break 
            else:      
                content = None
            if not content:                
                info = "Data požadovaného typu nenalezena"
            elif "ukazat" in answer:
                return HttpResponse(content, content_type='text/plain')
            else:
                filename = {"sezeni": "Sessions", "skupiny": "Groups", "vyherc": "Winners", "participant": "Participants", "nabidky": "Bids"}[key]
                return downloadData(content, filename)
        elif "stahnout" in answer:
            info = "Hotovo" 
            return(download(request))
        elif "preskocit" in answer:
            splitted = answer.split()
            if len(splitted) != 2:
                info = "Participantovo id neuvedeno správně"
            else:
                participant_id = splitted[1].strip()
                info = removeParticipant(participant_id)
        else:
            info = "Toto není validní příkaz"
    else:        
        try:
            currentSession = Session.objects.latest('start')
            participantsInSession = Participant.objects.filter(session = currentSession.session_number)
            numberOfParticipants = len(participantsInSession)
            status = currentSession.status 
            if status == "open":
                info = "Přihlášeno {} participantů do sezení {}, které nebylo zatím spuštěno".format(numberOfParticipants, currentSession.session_number)
            elif status == "ongoing":
                info = "Probíhá sezení {} s {} participanty".format(currentSession.session_number, numberOfParticipants)
                parts = Participant.objects.filter(session = currentSession.session_number, finished = True).order_by("time")
                for part in parts:
                    files = os.listdir(results_path())                    
                    filePresent = any(part.participant_id in file for file in files)
                    participants[part.participant_id] = {"reward": part.reward, "file": filePresent}
            elif status == "closed":
                info = "Přihlášeno {} participantů do sezení {}, které nebylo zatím spuštěno, ale je uzavřeno pro přihlašování".format(numberOfParticipants, currentSession.session_number)
            elif status == "finished":
                info = "Poslední sezení {} bylo ukončeno".format(currentSession.session_number)
        except ObjectDoesNotExist:
            info = "V databázi není žádné sezení"
        except Exception as e:
            info = e
    localContext = {"info": info, "status": status, "participants": participants}
    template = loader.get_template('index.html')
    return HttpResponse(template.render(localContext, request))