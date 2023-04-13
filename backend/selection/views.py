from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist

import random

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
            currentSession = Session.objects.latest('start')
            if currentSession.status == "open":
                try:
                    Participant.objects.get(participant_id = participant_id)
                    return HttpResponse("already_logged")
                    # participant = Participant.objects.get(participant_id = participant_id)
                    # if participant.frame == 0:
                    #     return HttpResponse("already_logged")
                    # else:
                    #     return HttpResponse("frame_" + str(participant.frame))
                except ObjectDoesNotExist:                    
                    currentSession.participants += 1
                    currentSession.save()
                    participant = Participant(participant_id = participant_id, group_number = -99, session = currentSession.session_number, frame = 0)
                    participant.save()         
                    return HttpResponse("login_successful")   
            elif currentSession.status == "ongoing":
                try:
                    participant = Participant.objects.get(participant_id = participant_id)
                    group = Group.objects.get(group_number = participant.group_number)
                    return HttpResponse("_".join(["start", str(group.bdm_one), str(group.bdm_two), group.condition]))
                except ObjectDoesNotExist:
                    return HttpResponse("ongoing")
            else:
                return HttpResponse("no_open")       
        else:
            participant = Participant.objects.get(participant_id = participant_id) 
            bid = Bid(participant_id = participant_id, block = block, bid = offer, group_number = participant.group_number)
            bid.save()            
            group = Group.objects.get(group_number = participant.group_number)
            group_bids = Bid.objects.filter(block = block, group_number = participant.group_number)
            if len(group_bids) == group.participants:
                highest_bidder = []
                maxoffer = 0
                secondoffer = 0
                all_members = Participant.objects.filter(group_number = participant.group_number)
                for p in all_members:
                    b = Bid.objects.get(participant_id = p.participant_id, block = block)
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
                winner = Winner(group_number = group.group_number, block = block, winner = highest_bidder, maxoffer = maxoffer, secondoffer = secondoffer)
                winner.save()
            return HttpResponse("ok")


@login_required(login_url='/admin/login/')
def openSession(request):
    otherSessions = Session.objects.filter(status = "open")
    for oldSession in otherSessions:
        oldSession.status = "closed"
    session = Session(status = "open")
    session.save()    
    return HttpResponse("Session {} otevřena".format(session.session_number))


@login_required(login_url='/admin/login/')
def closeSession(request):
    currentSession = Session.objects.get(status = "open")    
    currentSession.status = "closed"    
    currentSession.save()
    return HttpResponse("Session {} uzavřena".format(currentSession.session_number))


@login_required(login_url='/admin/login/')
def startSession(request):
    currentSession = Session.objects.latest('start')
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
        condition = random.choice(["low", "high"])
        group = Group(session = currentSession.session_number, participants = 4, bdm_one = bdm_one, bdm_two = bdm_two)
        group.save()
        for j in range(4):
            p = participants[num]
            p.group_number = group.group_number
            p.save()
            num += 1
    return HttpResponse("Session {} zahájena s {} participanty".format(currentSession.session_number, currentSession.participants))


@login_required(login_url='/admin/login/')
def sessionInfo(request):
    pass