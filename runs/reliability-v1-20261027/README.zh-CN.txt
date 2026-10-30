结构化工具可靠性初始评测 v1（量化 Qwen）

固定12个case，每个独立重复3次，共36轮；每轮最多25次实际API、80次工具。实际API 397 次，接口错误 0 次；真实GPT/其他模型调用0。
模型请求与响应标签：Qwen3.8-Flash-Next-AWQ-INT4，thinking=false；不能据此认证后端权重。

最终内容/业务条件正确：20/36；任务完成：34/36；正确且完成：18/36。
预算耗尽：2/36；发生无效工具操作：9/36，共12次；恢复后成功：4/9个出现可恢复拒绝的run。

分family（内容正确 / run数）：
W7: 8/18；完成 17/18；正确且完成 7/18。
W8: 9/12；完成 12/12；正确且完成 9/12。
W9: 3/6；完成 5/6；正确且完成 2/6。

整体run微平均：55.6%；12个case等权宏平均：55.6%（每case重复数相同，故等于微平均）；3个family等权宏平均：56.5%。
三次内容均正确的case：3/12；三次均正确且完成：2/12。这是重复稳定性，不是总体正确率。

配对比较（同基础输入和repeat；挑战减基线）：
W7-conflict: 6对，平均差 +16.7个百分点；基线对/挑战错 0；基线错/挑战对 1；两者错 3；两者对 2。
W7-coverage: 6对，平均差 +16.7个百分点；基线对/挑战错 2；基线错/挑战对 3；两者错 1；两者对 0。
W8-dynamic: 6对，平均差 +16.7个百分点；基线对/挑战错 0；基线错/挑战对 1；两者错 1；两者对 4。
W9-permanent: 3对，平均差 +100.0个百分点；基线对/挑战错 0；基线错/挑战对 3；两者错 0；两者对 0。

所有基线失败、未暴露故障和API故障均留在总体分母。W9故障暴露数见SUMMARY.json；未暴露不等于恢复成功或失败。错误分类只基于最终状态与工具拒绝等可见证据，不能确定原因时记unknown，不猜测模型内部思维。
W9六轮均未触发故障；其配对分数差来自相同费用4路径在不同可行最优费用条件下的判定，不表示永久故障更容易或恢复能力提高。
无效工具操作计数指runner异常拒绝；业务层可恢复拒绝另列。最终正确内容但未finish的两轮仍计入预算耗尽，不能称为正确且完成。
这是小型设计性样本：W7/W8主要是同一学生数据的行序/处理机制变体，W9为一个图；不能当成12个独立随机总体样本。重复run相关，本报告不提供显著性、排名或伪精确置信区间。

交付文件：MANIFEST.json（预定case/顺序/参考答案）；FROZEN-HASHES.json；ANALYSIS-PLAN.txt；runs.csv；SUMMARY.json；ERROR-EVIDENCE.json。每个case-*-attempt-*含原始响应、API账本、result.json、文件产物及audit/AUDIT.json。reference仅离线桩，不是模型成功证据。

用户GPT对照：全部12个case各1次，最多300次实际API，80工具/case。与Qwen repeat=1成对比较；增加GPT重复需用户另行决定。当前既有gateway.models.json的gpt alias为gpt-6-astra，脚本检查名称，不认证实际后端权重。费用取决于真实计费与token用量，此处不估算。
脚本默认只预览，只有明确-Execute才调用。复用你此前终端中的MODEL_BASE_URL、MODEL_API_KEY；缺失时脚本停止，不需要发送密钥。所有JSON由Python直接UTF-8写盘，PowerShell不解析控制台JSON。

PowerShell（项目根目录）：
$batch = 'E:\文档类\信通院\tooluser_pilot\runs\reliability-v1-20261027'
$out = Join-Path (Split-Path (Split-Path $batch -Parent) -Parent) ('runs\gpt-reliability-v1-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
& (Join-Path $batch "run-gpt-comparison.ps1") -OutputRoot $out
& (Join-Path $batch "run-gpt-comparison.ps1") -OutputRoot $out -Execute

断点续跑须使用同一个$out绝对路径：已完成result.json会跳过；未完成/状态不确定的case或残留RUNNING.lock会停止，先核查，不能删除目录后盲目重跑。更换输出目录会新启动整批，可能重复计费。
执行后返回$out目录路径，保留comparison-summary.json、各case/result.json、usage.sqlite、原始响应和artifact子目录。不要发送环境变量或密钥。

本地离线复核（不会调用模型）：
python "E:\文档类\信通院\tooluser_pilot\runs\reliability-v1-20261027\summarize.py"
python "E:\文档类\信通院\tooluser_pilot\runs\reliability-v1-20261027\error_evidence.py"
GPT脚本已用SDK替换桩离线验证12个case及续跑0新增调用；这不算真实GPT对照。