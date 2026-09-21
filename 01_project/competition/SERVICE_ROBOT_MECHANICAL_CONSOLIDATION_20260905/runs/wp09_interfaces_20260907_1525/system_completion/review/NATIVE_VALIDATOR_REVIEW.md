# 原生装配验收脚本的独立只读审查

独立输入检查 **5768/5768** 通过；两项新发现的哈希证据绑定缺陷，已由 native writer 修复并经独立源码复读确认。本审查没有调用 CAD、OCC、COM，也没有修改 native writer 文件。

[机器审查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/NATIVE_VALIDATOR_REVIEW.json>)记录每项检查和本次读到的代码SHA；[复核脚本](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/check_native_validator_inputs.py>)只读输入、只写review结果。源码正确及输入一致不等于装配运行已成功，三态集成/冷读/搬迁仍以实际回执验收。

## 已核对的坐标与数量合同

- 三态各873个唯一身份。原705中152个更新、553个保持；删除152后插入320个，即152个更新件和168个新增面层。
- 新源形状共138个：8个边框、2个面层共享形状、128个R01源坐标形体；4个canonical参考形状未计入装配。
- prepare最后以native_T_local_to_S回填T_S_local，所有873条期望变换两字段一致。553个保持件逐一与父本实际native冷读变换比较，只有mm/m浮点往返微差；旧82件的native坐标权威没有退回旧STEP坐标。
- R01的128个形体坐标已烘焙在整星S内，三态均使用identity装配变换。84个CIC和84个胶层的全部三态变换逐项匹配太阳布局；负翼贴父板local−Z、正翼贴local+Z，展开后CIC正面均朝整星+Z。

## 实际冷读检查的范围

集成按ComponentReference定位152个删除对象，插入320个对象后重新检查全部873个唯一身份。继承helper.metadata(measure=False)检查每个对象实际文件路径、SHA、native16变换、固定/抑制状态及总数；driver另检查依赖集合与期望完全相同、全部依赖在当前根目录内。

完整装配冷读不重新读取全部1254个实体。138个新native零件采用单独导入后冷读实体/体积/包络，保留件采用父本SHA证据。8个边框采用另行同内核往返等价证据，并保留SW体积标量不等价的记录。不能把这种组合证据写成1254个实体全部本轮实测。

## 两项缺陷与已复读的修复

初读发现integrate/cold给新零件的期望SHA直接赋当前待验文件SHA，随后比较成为自证；另一个缺口是cold未将待验SLDASM绑定到该状态的integration保存SHA。两项均已即时通知root和native writer。

最新源码已关闭这两个缺口：native_delta_seal_parts.py从完成的逐件导入原始native_save SHA建立一次性138件冻结清单，文件以独占创建方式写出；source/native路径、源SHA、全部形状ID和8frame往返证据均核验。driver采用此冻结SHA，当前文件哈希只用于比较。cold进一步匹配准确状态的PASS integration回执、保存SHA、输入manifest SHA和冻结清单SHA，并记录integration回执自身SHA。

封存器只接纳完成的逐件状态、实际冷读实体数/包络/体积验证标记与文件哈希。一个因后续资源限制失败的批次可以保留已完成且证据完整的零件，不因此继承整个失败批次的PASS。最终delivery再次检查该链及全部冷读记录。

## 实际搬迁的边界

driver的搬迁cold分支已在OpenDoc6之前和之后检查原C/cad不存在、新根不同；待验native文件使用新folder加原basename，期望SHA仍来自原冻结清单。因此不会为验证迁移而重新访问已移走的旧native绝对路径。完整依赖读回也必须全部在新根内。

仍须实际执行C/cad→C/d的搬迁，并在原根缺席时完成冷读，再按原SHA移回。delivery要求回迁完成、迁移回执中原根缺席为true、保存/依赖SHA与冻结结果相符。源码里的断言不能替代真实运行；本审查的actual_relocation_execution_verified和actual_native_execution_verified均为false。

此审查没有赋予连续机构、制造、飞行或完整机电功能完成信用。
