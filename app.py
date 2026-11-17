import os, sqlite3, time
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me')
DB = os.path.join(app.instance_path, 'schemes.db')
ALPHA = 0.6
EDU = {'secondary':1,'higher secondary':2,'undergraduate':3,'postgraduate':4,'doctorate':5}

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    os.makedirs(app.instance_path, exist_ok=True)
    con=db(); cur=con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, age INTEGER, income REAL, education TEXT, occupation TEXT, state TEXT, residence TEXT);
    CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT);
    CREATE TABLE IF NOT EXISTS schemes(id INTEGER PRIMARY KEY, name TEXT, ministry TEXT, category TEXT, description TEXT, benefits TEXT, min_age INTEGER, max_age INTEGER, income_limit REAL, education TEXT, occupation TEXT, state TEXT, residence TEXT, official_url TEXT, apply_url TEXT, last_updated TEXT);
    CREATE TABLE IF NOT EXISTS recommendations(id INTEGER PRIMARY KEY, user_id INTEGER, scheme_id INTEGER, score REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS user_scheme_history(id INTEGER PRIMARY KEY, user_id INTEGER, scheme_id INTEGER, action TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    if not cur.execute('SELECT 1 FROM admins').fetchone():
        cur.execute('INSERT INTO admins(username,password) VALUES(?,?)',('admin',generate_password_hash('admin123')))
    if not cur.execute('SELECT 1 FROM schemes').fetchone():
        samples=[
        ('Demo Student Education Support','Education Department','Scholarship','Financial support for students pursuing higher education','Tuition and study assistance',17,25,300000,'undergraduate','student','All India','Any','https://www.myscheme.gov.in/','https://www.myscheme.gov.in/','2026-11-01'),
        ('Demo Rural Learner Scholarship','Education Department','Scholarship','Scholarship assistance for rural students and learners','Education grant',16,28,250000,'higher secondary','student','All India','rural','https://www.myscheme.gov.in/','https://www.myscheme.gov.in/','2026-11-01'),
        ('Demo Youth Skill Development','Skill Development Department','Employment','Skill training and employability support for young people','Training and certification',18,35,500000,None,None,'All India','Any','https://www.myscheme.gov.in/','https://www.myscheme.gov.in/','2026-11-01'),
        ('Demo Farmer Assistance','Agriculture Department','Agriculture','Income and agricultural assistance for farmers','Agricultural support',18,65,400000,None,'farmer','All India','rural','https://www.myscheme.gov.in/','https://www.myscheme.gov.in/','2026-11-01'),
        ('Demo Uttarakhand Student Aid','State Education Department','Scholarship','Education support for students residing in Uttarakhand','Student financial assistance',17,30,350000,'undergraduate','student','Uttarakhand','Any','https://www.myscheme.gov.in/','https://www.myscheme.gov.in/','2026-11-01')]
        cur.executemany('''INSERT INTO schemes(name,ministry,category,description,benefits,min_age,max_age,income_limit,education,occupation,state,residence,official_url,apply_url,last_updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',samples)
    con.commit(); con.close()

def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*a,**k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get('admin'): return redirect(url_for('admin_login'))
        return f(*a,**k)
    return w

def evaluate(user, s):
    checks=[]; passed=0; specified=0; failed=[]
    def add(label, ok, reason):
        nonlocal passed,specified
        specified += 1
        if ok: passed += 1; checks.append('✓ '+label)
        else: failed.append(reason)
    if s['min_age'] is not None: add('minimum age', user['age'] is None or user['age']>=s['min_age'], f"Minimum age is {s['min_age']}")
    if s['max_age'] is not None: add('maximum age', user['age'] is None or user['age']<=s['max_age'], f"Maximum age is {s['max_age']}")
    if s['income_limit'] is not None: add('income', user['income'] is None or user['income']<=s['income_limit'], f"Income must be at most ₹{s['income_limit']:,.0f}")
    if s['education']:
        ok = not user['education'] or EDU.get(user['education'].lower(),0)>=EDU.get(s['education'].lower(),0)
        add('education',ok,f"Minimum education is {s['education']}")
    if s['occupation']: add('occupation', not user['occupation'] or user['occupation'].lower()==s['occupation'].lower(), f"Occupation required: {s['occupation']}")
    if s['state'] and s['state'].lower()!='all india': add('state', not user['state'] or user['state'].lower()==s['state'].lower(), f"Available in {s['state']} only")
    if s['residence'] and s['residence'].lower()!='any': add('residence', not user['residence'] or user['residence'].lower()==s['residence'].lower(), f"Residence required: {s['residence']}")
    return not failed, (passed/specified if specified else 1.0), checks, failed

def recommend(user):
    con=db(); schemes=con.execute('SELECT * FROM schemes').fetchall(); con.close()
    eligible=[]; rejected=[]
    for s in schemes:
        ok,e,checks,fails=evaluate(user,s)
        if ok: eligible.append([s,e,checks])
        else: rejected.append((s,fails))
    if not eligible: return [],rejected
    corpus=[f"{x[0]['name']} {x[0]['category']} {x[0]['description']} {x[0]['benefits']}" for x in eligible]
    profile=f"{user['occupation'] or ''} {user['education'] or ''} {user['residence'] or ''} {user['state'] or ''} education scholarship employment agriculture financial assistance"
    vec=TfidfVectorizer(stop_words='english',ngram_range=(1,2)); mat=vec.fit_transform(corpus+[profile]); sims=cosine_similarity(mat[-1],mat[:-1]).flatten()
    out=[]
    for (s,e,checks),r in zip(eligible,sims):
        score=ALPHA*e+(1-ALPHA)*float(r)
        out.append({'scheme':s,'eligibility':e,'relevance':float(r),'score':score,'checks':checks})
    return sorted(out,key=lambda x:x['score'],reverse=True),rejected

@app.route('/')
def home(): return render_template('home.html')
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        try:
            con=db(); con.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(request.form['name'],request.form['email'].lower(),generate_password_hash(request.form['password']))); con.commit(); con.close(); flash('Account created. Please log in.','success'); return redirect(url_for('login'))
        except sqlite3.IntegrityError: flash('Email already registered.','danger')
    return render_template('register.html')
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        con=db(); u=con.execute('SELECT * FROM users WHERE email=?',(request.form['email'].lower(),)).fetchone(); con.close()
        if u and check_password_hash(u['password'],request.form['password']): session.clear(); session['user_id']=u['id']; return redirect(url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))
@app.route('/dashboard')
@login_required
def dashboard():
    con=db(); u=con.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); count=con.execute('SELECT COUNT(*) c FROM recommendations WHERE user_id=?',(u['id'],)).fetchone()['c']; con.close(); return render_template('dashboard.html',u=u,count=count)
@app.route('/profile',methods=['GET','POST'])
@login_required
def profile():
    con=db()
    if request.method=='POST':
        con.execute('UPDATE users SET name=?,age=?,income=?,education=?,occupation=?,state=?,residence=? WHERE id=?',(request.form['name'],request.form.get('age') or None,request.form.get('income') or None,request.form.get('education'),request.form.get('occupation'),request.form.get('state'),request.form.get('residence'),session['user_id'])); con.commit(); flash('Profile updated.','success')
    u=con.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); con.close(); return render_template('profile.html',u=u)
@app.route('/recommendations')
@login_required
def recommendations():
    con=db(); u=con.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); con.close()
    if u['age'] is None: flash('Complete your profile first.','warning'); return redirect(url_for('profile'))
    t=time.perf_counter(); results,rejected=recommend(u); elapsed=(time.perf_counter()-t)*1000
    con=db(); con.execute('DELETE FROM recommendations WHERE user_id=?',(u['id'],));
    for r in results: con.execute('INSERT INTO recommendations(user_id,scheme_id,score) VALUES(?,?,?)',(u['id'],r['scheme']['id'],r['score']))
    con.commit(); con.close(); return render_template('recommendations.html',results=results,rejected=rejected,elapsed=elapsed)
@app.route('/history')
@login_required
def history():
    con=db(); rows=con.execute('''SELECT r.*,s.name FROM recommendations r JOIN schemes s ON s.id=r.scheme_id WHERE r.user_id=? ORDER BY r.created_at DESC''',(session['user_id'],)).fetchall(); con.close(); return render_template('history.html',rows=rows)
@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        con=db(); a=con.execute('SELECT * FROM admins WHERE username=?',(request.form['username'],)).fetchone(); con.close()
        if a and check_password_hash(a['password'],request.form['password']): session.clear(); session['admin']=True; return redirect(url_for('admin'))
        flash('Invalid admin credentials.','danger')
    return render_template('admin_login.html')
@app.route('/admin')
@admin_required
def admin():
    con=db(); schemes=con.execute('SELECT * FROM schemes ORDER BY id DESC').fetchall(); con.close(); return render_template('admin.html',schemes=schemes)
@app.route('/admin/scheme',methods=['POST'])
@admin_required
def add_scheme():
    f=request.form; con=db(); con.execute('''INSERT INTO schemes(name,ministry,category,description,benefits,min_age,max_age,income_limit,education,occupation,state,residence,official_url,apply_url,last_updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,date('now'))''',(f['name'],f['ministry'],f['category'],f['description'],f['benefits'],f.get('min_age') or None,f.get('max_age') or None,f.get('income_limit') or None,f.get('education') or None,f.get('occupation') or None,f.get('state') or 'All India',f.get('residence') or 'Any',f.get('official_url'),f.get('apply_url'))); con.commit(); con.close(); flash('Scheme added.','success'); return redirect(url_for('admin'))
@app.route('/admin/delete/<int:sid>',methods=['POST'])
@admin_required
def delete_scheme(sid):
    con=db(); con.execute('DELETE FROM schemes WHERE id=?',(sid,)); con.commit(); con.close(); return redirect(url_for('admin'))

init_db()
if __name__=='__main__': app.run(debug=True)
