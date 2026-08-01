# 第 11 步：批量运行 10 个 RE1-OB 案例

这一阶段不再手工重复修改 `--case-path`，而是让程序自动发现 5 个服务的
delay/loss 案例，并对每个案例运行 3 种方法。

## 运行命令

在项目根目录 `D:\Project\RCA` 中执行：

```powershell
conda activate fastapi_env
python -m scripts.run_batch
```

这里使用 `python -m`，表示按 Python 模块启动。这样项目根目录会进入模块搜索
路径，`scripts` 和 `src` 之间的导入关系更稳定。

只重新计算报告、不重新运行算法：

```powershell
python -m scripts.evaluate_results
```

## 默认实验范围

- 服务：`adservice`、`cartservice`、`checkoutservice`、`currencyservice`、
  `productcatalogservice`
- 故障：`delay`、`loss`
- 实例：每种服务/故障组合的实例 `1`
- 方法：PyRCA EpsilonDiagnosis、RCAEval BARO、RCAEval E-Diagnosis
- 总量：10 个案例 × 3 种方法 = 30 次运行

## 输出文件

- `outputs/predictions/re1_ob_delay_loss/*.json`：每次运行的统一原始结果
- `outputs/reports/re1_ob_delay_loss/case_results.csv`：逐案例评价
- `outputs/reports/re1_ob_delay_loss/algorithm_comparison.csv`：算法汇总
- `outputs/reports/re1_ob_delay_loss/algorithm_comparison.md`：可读报告
- `outputs/reports/re1_ob_delay_loss/algorithm_comparison.xlsx`：带格式的 Excel 报告

## 需要理解的评价指标

- 服务级命中：预测指标属于正确服务即可，例如预测
  `adservice_mem` 也算找到了 `adservice`。
- 指标级命中：服务和指标都要正确，例如 delay/loss 的答案是
  `adservice_latency`。
- Hit@K：正确答案是否出现在前 K 名。
- MRR：正确答案首次出现的排名取倒数；第 1 名为 1，第 2 名为 0.5，未命中为 0。

先看服务级指标判断“是否找对微服务”，再看指标级指标判断“是否进一步找对
故障指标”。两种口径不能混在一起。
