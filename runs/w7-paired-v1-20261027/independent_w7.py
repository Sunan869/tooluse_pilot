"""SQL oracle independent of environment's Python grader."""
import sqlite3
def oracle(data):
    db=sqlite3.connect(':memory:')
    db.execute('create table enrollment(record_id,student_id,name,batch_id,status)')
    db.execute('create table grades(record_id,student_id,batch_id,revision integer,score integer,published integer,valid integer)')
    db.executemany('insert into enrollment values(?,?,?,?,?)',[(r['record_id'],r['student_id'],r['name'],r['batch_id'],r['status']) for r in data['enrollment']])
    db.executemany('insert into grades values(?,?,?,?,?,?,?)',[(r['record_id'],r['student_id'],r['batch_id'],r['revision'],r['score'],r['published'],r['valid']) for r in data['grades']])
    rows=db.execute('''with ranked as (
      select *,row_number() over(partition by student_id,batch_id order by revision desc) as rn
      from grades where batch_id=? and published=1 and valid=1)
      select e.student_id,e.name,g.score,g.batch_id,g.record_id,e.record_id
      from enrollment e join ranked g on e.student_id=g.student_id and e.batch_id=g.batch_id
      where e.batch_id=? and e.status='active' and g.rn=1
      order by g.score desc,e.student_id asc limit 3''',(data['target_batch'],data['target_batch'])).fetchall()
    db.close();return [list(r) for r in rows]
