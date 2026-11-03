import json,copy
from pathlib import Path
from w7_data import dataset
TASK='''请制作本校 B2 active 学生最新已发布有效成绩的 Top 3 XLSX，按分数降序、同分 student_id 升序；按 ID 和批次关联，不按姓名或跨批次合计。输出列 student_id、name、score、batch_id、grade_record_id、enrollment_record_id。先查目录确认权威来源。任务期间可能有一次确定性成绩版本发布：在首次成绩读取完成后，或未读成绩就首次写入之前发生；之后不再变化。每次读取注明 read_revision/current_revision，get_status 可查询当前版本与变更记录。读完后、提交前必须核验版本；版本变化时通过重读权威来源更新答案。缓存不作为权威。write_submission 使用 expected_revision 防止过期写入；拒绝后可查询并重读恢复。可以多次覆盖提交直到 finish。finish 是最终不可撤销的结束，runner 收到成功后立刻停止，之后不会再调用模型或执行排队工具；请在 finish 前核验保存内容和版本。工具不告诉你答案是否正确。'''
def create(folder,condition,seed=20261027):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=False);d=dataset(seed)
 case={'id':f'w8-{condition}-{seed}','family':'real_w8','condition':condition,'seed':seed,'task':TASK,'input':{'dataset':'dataset.json'}}
 for name,obj in [('candidate.json',case),('dataset.json',d)]: (folder/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 return case,d
