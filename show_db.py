from pprint import pprint
import app

print('\n--- USERS ---')
try:
    users = app.users
    ulist = []
    for u in users.find():
        ulist.append(u)
    pprint(ulist)
except Exception as e:
    print('Error reading users:', e)

print('\n--- MEDIA ---')
try:
    media = app.media_coll
    mlist = []
    for m in media.find():
        mlist.append(m)
    pprint(mlist)
except Exception as e:
    print('Error reading media:', e)

print('\n--- COMMENTS ---')
try:
    comments = app.comments_coll
    clist = []
    for c in comments.find():
        clist.append(c)
    pprint(clist)
except Exception as e:
    print('Error reading comments:', e)
