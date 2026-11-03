import json,random
from pathlib import Path
TASK='''请生成本校 B2 批次数学成绩 Top 3 的 XLSX。只考虑 B2 学籍状态为 active 的学生；以教务权威明细中该学生 B2 已发布且有效的最高 revision 成绩为准。不能跨批次合计，也不能按姓名合并学生。按分数降序、同分 student_id 升序排序，取前三；不足三人则返回全部。请给 student_id、姓名、分数、batch_id 及教务成绩/学籍来源 record_id。先查目录了解来源职责与字段，注意返回数据是否完整；缓存仅用于定位，不是成绩或资格权威。允许任何合法补查路径，不要求读取无用缓存。使用 write_submission 写入结果并 finish；finish 不会替你校正答案。'''
def dataset(seed):
    names=['陈晨','陈晨','林悦','周航','赵宁','许安','吴桐','孙晴']
    enrollment=[{'record_id':f'e-s{i:02d}','student_id':f's{i:02d}','name':name,'batch_id':'B2','status':'inactive' if i==4 else 'active'} for i,name in enumerate(names,1)]
    grades=[]
    for batch,values in [('B1',[100,55,60,98,93,89,100,96]),('B2',[92,86,95,99,90,91,88,91])]:
        for i,score in enumerate(values,1):
            revision=2 if batch=='B2' and i in [2,6] else 1
            grades.append({'record_id':f'g-{batch}-s{i:02d}-r{revision}','student_id':f's{i:02d}','batch_id':batch,'revision':revision,'score':score,'published':True,'valid':True,'supersedes':f'g-{batch}-s{i:02d}-r1' if revision==2 else None})
    for i,score in [(2,99),(6,89)]:grades.append({'record_id':f'g-B2-s{i:02d}-r1','student_id':f's{i:02d}','batch_id':'B2','revision':1,'score':score,'published':True,'valid':True,'supersedes':None})
    cache=[{'record_id':f'c-s{i:02d}','student_id':f's{i:02d}','name':name,'batch_id':'B2','score':score,'score_record_id':f'g-B2-s{i:02d}-r'+('2' if i in [2,6] else '1'),'as_of_revision':2 if i in [2,6] else 1} for i,(name,score) in enumerate(zip(names,[92,86,95,99,90,91,88,91]),1)]
    rng=random.Random(seed)
    for rows in [enrollment,grades,cache]:rng.shuffle(rows)
    return {'snapshot_id':'W7-SNAPSHOT-001','target_batch':'B2','enrollment':enrollment,'grades':grades,'cache':cache}
def create(folder,condition,seed=20261027):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    data=dataset(seed);case={'id':f'w7-{condition}-{seed}','family':'real_w7','condition':condition,'seed':seed,'task':TASK,'input':{'dataset':'dataset.json'}}
    (folder/'dataset.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'candidate.json').write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf-8')
    return case,data
