import random, time
from app import app, db, recommend
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
random.seed(42)
profiles=[]
for i in range(100):
    profiles.append({'id':-1,'age':random.randint(16,65),'income':random.randint(100000,700000),'education':random.choice(['secondary','higher secondary','undergraduate','postgraduate']),'occupation':random.choice(['student','farmer','employed']),'state':random.choice(['Uttarakhand','Delhi','Uttar Pradesh']),'residence':random.choice(['rural','urban'])})
y_true=[]; y_pred=[]; times=[]
with app.app_context():
    schemes=db().execute('SELECT * FROM schemes').fetchall()
    from app import evaluate
    for u in profiles:
        t=time.perf_counter(); results,_=recommend(u); times.append((time.perf_counter()-t)*1000); ids={r['scheme']['id'] for r in results}
        for s in schemes:
            truth=evaluate(u,s)[0]
            y_true.append(int(truth)); y_pred.append(int(s['id'] in ids))
print('Precision:',round(precision_score(y_true,y_pred,zero_division=0),4))
print('Recall:',round(recall_score(y_true,y_pred,zero_division=0),4))
print('F1:',round(f1_score(y_true,y_pred,zero_division=0),4))
print('Accuracy:',round(accuracy_score(y_true,y_pred),4))
print('Avg response time (ms):',round(sum(times)/len(times),2))
