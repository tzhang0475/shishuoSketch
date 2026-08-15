# H0A 时间缺口审计

本审计覆盖当前全部生产 Story。unknown 与 phase_only 都是合法结果，不是必须消灭的缺陷。

- Story 总数：83
- genuine_unknown：54
- source conflict：0
- event-linked：13

## 仍为 unknown 的 Story

01-dexing-017、01-dexing-026、01-dexing-045、02-yanyu-035、02-yanyu-036、02-yanyu-069、02-yanyu-071、02-yanyu-079、02-yanyu-083、02-yanyu-086、03-zhengshi-022、04-wenxue-022、04-wenxue-024、04-wenxue-036、04-wenxue-087、05-fangzheng-023、05-fangzheng-027、05-fangzheng-028、05-fangzheng-051、05-fangzheng-053、05-fangzheng-055、05-fangzheng-058、06-yaliang-017、06-yaliang-019、06-yaliang-027、06-yaliang-029、07-shijian-018、07-shijian-021、08-shangyu-034、08-shangyu-043、08-shangyu-077、08-shangyu-079、09-pinzao-006、09-pinzao-014、09-pinzao-017、09-pinzao-022、09-pinzao-026、09-pinzao-030、09-pinzao-036、09-pinzao-045、09-pinzao-063、10-guizhen-012、14-rongzhi-024、17-shangshi-008、19-xianyuan-026、22-chongli-002、23-rendan-001、23-rendan-026、23-rendan-038、25-paidiao-015、25-paidiao-026、25-paidiao-060、26-qingdi-002、33-youhui-007

## 分类

| Story | precision | gap class | 说明 |
|---|---|---|---|
| `01-dexing-012` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `01-dexing-014` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `01-dexing-015` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `01-dexing-016` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `01-dexing-017` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `01-dexing-023` | `event_bounded` | `event_known_date_uncertain` | 本则证据直接连接到永嘉之亂與南渡；显示事件范围，不把事件关联扩大为人物关系。 |
| `01-dexing-025` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `01-dexing-026` | `unknown` | `event_known_date_uncertain` | 仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。 |
| `01-dexing-045` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `02-yanyu-035` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `02-yanyu-036` | `unknown` | `event_known_date_uncertain` | 仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。 |
| `02-yanyu-069` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `02-yanyu-071` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `02-yanyu-078` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `02-yanyu-079` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `02-yanyu-083` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `02-yanyu-086` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `02-yanyu-107` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `03-zhengshi-006` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `03-zhengshi-022` | `unknown` | `event_known_date_uncertain` | 仅有早先背景或引述，不能当作本则故事时间。 |
| `04-wenxue-022` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `04-wenxue-024` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `04-wenxue-036` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `04-wenxue-069` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `04-wenxue-087` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `05-fangzheng-012` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `05-fangzheng-023` | `unknown` | `event_known_date_uncertain` | 仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。 |
| `05-fangzheng-025` | `event_bounded` | `event_known_date_uncertain` | 本则证据直接连接到永嘉之亂與南渡；显示事件范围，不把事件关联扩大为人物关系。 |
| `05-fangzheng-027` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `05-fangzheng-028` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `05-fangzheng-031` | `event_bounded` | `event_known_date_uncertain` | 本则证据直接连接到王敦之亂；显示事件范围，不把事件关联扩大为人物关系。 |
| `05-fangzheng-032` | `event_bounded` | `event_known_date_uncertain` | 本则证据直接连接到王敦之亂；显示事件范围，不把事件关联扩大为人物关系。 |
| `05-fangzheng-051` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `05-fangzheng-053` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `05-fangzheng-055` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `05-fangzheng-058` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `06-yaliang-017` | `unknown` | `event_known_date_uncertain` | 仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。 |
| `06-yaliang-019` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `06-yaliang-027` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `06-yaliang-029` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `07-shijian-005` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `07-shijian-018` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `07-shijian-021` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `08-shangyu-006` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `08-shangyu-019` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `08-shangyu-034` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `08-shangyu-043` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `08-shangyu-051` | `event_bounded` | `event_known_date_uncertain` | 本则证据直接连接到永嘉之亂與南渡；显示事件范围，不把事件关联扩大为人物关系。 |
| `08-shangyu-077` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `08-shangyu-079` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-006` | `unknown` | `event_known_date_uncertain` | 仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。 |
| `09-pinzao-008` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `09-pinzao-014` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-017` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-022` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-026` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-030` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-036` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-045` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `09-pinzao-063` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `10-guizhen-012` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `11-jiewu-005` | `event_bounded` | `event_known_date_uncertain` | 本则证据直接连接到王敦之亂；显示事件范围，不把事件关联扩大为人物关系。 |
| `14-rongzhi-005` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `14-rongzhi-024` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `17-shangshi-002` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `17-shangshi-008` | `unknown` | `event_known_date_uncertain` | 仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。 |
| `19-xianyuan-013` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `19-xianyuan-026` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `20-shujie-005` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `22-chongli-002` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `23-rendan-001` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `23-rendan-013` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `23-rendan-026` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `23-rendan-038` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `24-jianao-001` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `25-paidiao-009` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |
| `25-paidiao-015` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `25-paidiao-026` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `25-paidiao-060` | `unknown` | `event_known_date_uncertain` | 仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。 |
| `26-qingdi-002` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `27-jiajue-008` | `event_bounded` | `event_known_date_uncertain` | 本则证据直接连接到蘇峻之亂；显示事件范围，不把事件关联扩大为人物关系。 |
| `33-youhui-007` | `unknown` | `genuine_unknown` | 当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。 |
| `35-huoni-003` | `phase_only` | `phase_only` | 沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。 |

下一步是审阅这些缺口，而不是在 H0A 中下载新来源或强行补年。
