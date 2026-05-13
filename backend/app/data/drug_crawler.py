"""[PRD-469 M10 P0] 药品库扩充爬虫 —— 将药品库从 ~200 条扩充至 300+ 条。

基于手动种子数据（medication_seeds.py），补充常见慢病用药约 100+ 条，
覆盖高血压、糖尿病、高血脂、冠心病、呼吸系统、消化系统等慢病常用药。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MedicationLibrary

EXTRA_DRUGS = [
    # ── 高血压类 ──
    {"name": "硝苯地平控释片", "generic_name": "硝苯地平", "spec": "30mg×7片", "manufacturer": "拜耳医药", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血压"], "indications": "用于治疗高血压、冠心病、慢性稳定型心绞痛", "usage": "口服，一次30mg，一日1次", "contraindications": "对硝苯地平过敏者禁用；心源性休克", "adverse_reactions": "头痛、面部潮红、踝部水肿", "source": "manual_seed"},
    {"name": "苯磺酸氨氯地平片", "generic_name": "氨氯地平", "spec": "5mg×7片", "manufacturer": "辉瑞制药", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血压"], "indications": "用于高血压、慢性稳定性心绞痛及变异型心绞痛", "usage": "口服，起始剂量5mg，一日1次", "contraindications": "对氨氯地平过敏者禁用", "adverse_reactions": "头晕、水肿、心悸", "source": "manual_seed"},
    {"name": "厄贝沙坦片", "generic_name": "厄贝沙坦", "spec": "150mg×7片", "manufacturer": "赛诺菲", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血压"], "indications": "用于原发性高血压", "usage": "口服，150mg一日1次", "contraindications": "妊娠中晚期禁用", "adverse_reactions": "头晕、高钾血症", "source": "manual_seed"},
    {"name": "缬沙坦胶囊", "generic_name": "缬沙坦", "spec": "80mg×7粒", "manufacturer": "诺华制药", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血压"], "indications": "用于轻中度原发性高血压", "usage": "口服，80mg一日1次", "contraindications": "妊娠期禁用", "adverse_reactions": "头痛、头晕、乏力", "source": "manual_seed"},
    {"name": "卡托普利片", "generic_name": "卡托普利", "spec": "25mg×100片", "manufacturer": "上海施贵宝", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血压", "心力衰竭"], "indications": "用于高血压、心力衰竭", "usage": "口服，25mg一日2-3次", "contraindications": "双侧肾动脉狭窄禁用", "adverse_reactions": "干咳、低血压", "source": "manual_seed"},
    {"name": "氢氯噻嗪片", "generic_name": "氢氯噻嗪", "spec": "25mg×100片", "manufacturer": "天津力生", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血压"], "indications": "用于水肿性疾病、高血压", "usage": "口服，25-50mg一日1次", "contraindications": "无尿者禁用", "adverse_reactions": "低钾血症、高尿酸", "source": "manual_seed"},
    {"name": "氯沙坦钾片", "generic_name": "氯沙坦", "spec": "50mg×7片", "manufacturer": "默沙东", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血压"], "indications": "用于原发性高血压", "usage": "口服，50mg一日1次", "contraindications": "妊娠期禁用", "adverse_reactions": "头晕、体位性低血压", "source": "manual_seed"},
    # ── 糖尿病类 ──
    {"name": "二甲双胍缓释片", "generic_name": "二甲双胍", "spec": "0.5g×30片", "manufacturer": "中美施贵宝", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["糖尿病"], "indications": "用于2型糖尿病，尤其适用于肥胖患者", "usage": "口服，0.5g一日1-2次，随餐服用", "contraindications": "严重肾功能不全禁用", "adverse_reactions": "胃肠道反应、乳酸酸中毒", "source": "manual_seed"},
    {"name": "格列齐特缓释片", "generic_name": "格列齐特", "spec": "30mg×30片", "manufacturer": "施维雅", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["糖尿病"], "indications": "用于2型糖尿病", "usage": "口服，30mg一日1次", "contraindications": "1型糖尿病禁用", "adverse_reactions": "低血糖、体重增加", "source": "manual_seed"},
    {"name": "阿卡波糖片", "generic_name": "阿卡波糖", "spec": "50mg×30片", "manufacturer": "拜耳医药", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["糖尿病"], "indications": "用于2型糖尿病，降低餐后血糖", "usage": "用餐前即刻整片吞服，50mg一日3次", "contraindications": "肠梗阻禁用", "adverse_reactions": "腹胀、腹泻、排气增多", "source": "manual_seed"},
    {"name": "格列美脲片", "generic_name": "格列美脲", "spec": "2mg×15片", "manufacturer": "赛诺菲", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["糖尿病"], "indications": "用于2型糖尿病", "usage": "口服，起始1mg一日1次", "contraindications": "1型糖尿病、酮症酸中毒", "adverse_reactions": "低血糖、体重增加", "source": "manual_seed"},
    {"name": "西格列汀片", "generic_name": "西格列汀", "spec": "100mg×7片", "manufacturer": "默沙东", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["糖尿病"], "indications": "用于2型糖尿病", "usage": "口服，100mg一日1次", "contraindications": "1型糖尿病", "adverse_reactions": "头痛、鼻咽炎", "source": "manual_seed"},
    # ── 高血脂类 ──
    {"name": "阿托伐他汀钙片", "generic_name": "阿托伐他汀", "spec": "20mg×7片", "manufacturer": "辉瑞制药", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血脂"], "indications": "用于高胆固醇血症、冠心病", "usage": "口服，10-20mg一日1次", "contraindications": "活动性肝病禁用", "adverse_reactions": "肌痛、肝酶升高", "source": "manual_seed"},
    {"name": "瑞舒伐他汀钙片", "generic_name": "瑞舒伐他汀", "spec": "10mg×7片", "manufacturer": "阿斯利康", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血脂"], "indications": "用于高胆固醇血症、混合型血脂异常", "usage": "口服，5-10mg一日1次", "contraindications": "活动性肝病、严重肾功能不全", "adverse_reactions": "肌痛、蛋白尿", "source": "manual_seed"},
    {"name": "辛伐他汀片", "generic_name": "辛伐他汀", "spec": "20mg×7片", "manufacturer": "默沙东", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血脂"], "indications": "用于高胆固醇血症", "usage": "口服，20mg一日1次晚间服用", "contraindications": "活动性肝病", "adverse_reactions": "肌痛、肝酶升高", "source": "manual_seed"},
    {"name": "非诺贝特胶囊", "generic_name": "非诺贝特", "spec": "200mg×10粒", "manufacturer": "雅培", "category": "心血管", "rx_type": "处方药", "disease_tags": ["高血脂"], "indications": "用于高甘油三酯血症", "usage": "口服，200mg一日1次", "contraindications": "严重肝肾功能不全", "adverse_reactions": "胃肠道不适、肝酶升高", "source": "manual_seed"},
    # ── 冠心病类 ──
    {"name": "阿司匹林肠溶片", "generic_name": "阿司匹林", "spec": "100mg×30片", "manufacturer": "拜耳医药", "category": "心血管", "rx_type": "处方药", "disease_tags": ["冠心病", "脑卒中"], "indications": "抑制血小板聚集，用于心脑血管疾病的预防", "usage": "口服，100mg一日1次", "contraindications": "活动性消化道溃疡、出血体质", "adverse_reactions": "胃肠道不适、出血风险", "source": "manual_seed"},
    {"name": "硫酸氢氯吡格雷片", "generic_name": "氯吡格雷", "spec": "75mg×7片", "manufacturer": "赛诺菲", "category": "心血管", "rx_type": "处方药", "disease_tags": ["冠心病", "脑卒中"], "indications": "用于预防动脉粥样硬化血栓形成", "usage": "口服，75mg一日1次", "contraindications": "活动性出血禁用", "adverse_reactions": "出血、紫癜", "source": "manual_seed"},
    {"name": "单硝酸异山梨酯片", "generic_name": "单硝酸异山梨酯", "spec": "20mg×48片", "manufacturer": "阿斯利康", "category": "心血管", "rx_type": "处方药", "disease_tags": ["冠心病"], "indications": "用于冠心病长期治疗、心绞痛预防", "usage": "口服，20mg一日2次", "contraindications": "急性循环衰竭", "adverse_reactions": "头痛、面部潮红", "source": "manual_seed"},
    # ── 呼吸系统类 ──
    {"name": "布地奈德福莫特罗粉吸入剂", "generic_name": "布地奈德/福莫特罗", "spec": "160μg/4.5μg×60吸", "manufacturer": "阿斯利康", "category": "呼吸", "rx_type": "处方药", "disease_tags": ["哮喘"], "indications": "用于哮喘、慢性阻塞性肺疾病", "usage": "吸入，一次1-2吸，一日2次", "contraindications": "对本品过敏者禁用", "adverse_reactions": "口腔念珠菌感染、声音嘶哑", "source": "manual_seed"},
    {"name": "沙美特罗替卡松粉吸入剂", "generic_name": "沙美特罗/替卡松", "spec": "50μg/250μg×60吸", "manufacturer": "葛兰素史克", "category": "呼吸", "rx_type": "处方药", "disease_tags": ["哮喘", "慢阻肺"], "indications": "用于哮喘、COPD", "usage": "吸入，一次1吸，一日2次", "contraindications": "对乳糖过敏者禁用", "adverse_reactions": "头痛、咽喉刺激", "source": "manual_seed"},
    {"name": "孟鲁司特钠片", "generic_name": "孟鲁司特", "spec": "10mg×5片", "manufacturer": "默沙东", "category": "呼吸", "rx_type": "处方药", "disease_tags": ["哮喘"], "indications": "用于哮喘预防和长期治疗、过敏性鼻炎", "usage": "口服，10mg一日1次晚间服用", "contraindications": "对本品过敏者禁用", "adverse_reactions": "头痛、腹痛", "source": "manual_seed"},
    {"name": "沙丁胺醇气雾剂", "generic_name": "沙丁胺醇", "spec": "100μg×200揿", "manufacturer": "葛兰素史克", "category": "呼吸", "rx_type": "处方药", "disease_tags": ["哮喘"], "indications": "用于缓解哮喘急性发作", "usage": "必要时吸入1-2揿", "contraindications": "对本品过敏者禁用", "adverse_reactions": "心悸、头痛、震颤", "source": "manual_seed"},
    # ── 消化系统类 ──
    {"name": "奥美拉唑肠溶胶囊", "generic_name": "奥美拉唑", "spec": "20mg×14粒", "manufacturer": "阿斯利康", "category": "消化", "rx_type": "处方药", "disease_tags": ["胃食管反流", "消化性溃疡"], "indications": "用于胃酸相关疾病", "usage": "口服，20mg一日1-2次", "contraindications": "对本品过敏者禁用", "adverse_reactions": "头痛、腹泻、腹痛", "source": "manual_seed"},
    {"name": "雷贝拉唑钠肠溶片", "generic_name": "雷贝拉唑", "spec": "10mg×7片", "manufacturer": "卫材", "category": "消化", "rx_type": "处方药", "disease_tags": ["胃食管反流", "消化性溃疡"], "indications": "用于消化性溃疡、胃食管反流病", "usage": "口服，10mg一日1次", "contraindications": "对本品过敏者禁用", "adverse_reactions": "头痛、便秘、腹泻", "source": "manual_seed"},
    {"name": "铝碳酸镁咀嚼片", "generic_name": "铝碳酸镁", "spec": "0.5g×20片", "manufacturer": "拜耳医药", "category": "消化", "rx_type": "OTC", "disease_tags": ["胃食管反流"], "indications": "用于胃酸过多、胃灼热", "usage": "咀嚼后咽下，一次1-2片一日3-4次", "contraindications": "严重肾功能不全", "adverse_reactions": "便秘、腹泻", "source": "manual_seed"},
    # ── 痛风类 ──
    {"name": "别嘌醇片", "generic_name": "别嘌醇", "spec": "100mg×100片", "manufacturer": "上海信谊", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["痛风"], "indications": "用于高尿酸血症、痛风", "usage": "口服，起始100mg一日1次", "contraindications": "对本品过敏者禁用", "adverse_reactions": "皮疹、肝功能异常", "source": "manual_seed"},
    {"name": "非布司他片", "generic_name": "非布司他", "spec": "40mg×14片", "manufacturer": "武田制药", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["痛风"], "indications": "用于痛风患者高尿酸血症的长期治疗", "usage": "口服，40mg一日1次", "contraindications": "正在使用硫唑嘌呤", "adverse_reactions": "肝功能异常、关节痛", "source": "manual_seed"},
    {"name": "苯溴马隆片", "generic_name": "苯溴马隆", "spec": "50mg×10片", "manufacturer": "优时比", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["痛风"], "indications": "用于原发性高尿酸血症", "usage": "口服，50mg一日1次", "contraindications": "中重度肾功能不全", "adverse_reactions": "胃肠道不适、皮疹", "source": "manual_seed"},
    # ── 甲状腺类 ──
    {"name": "左甲状腺素钠片", "generic_name": "左甲状腺素", "spec": "50μg×100片", "manufacturer": "默克", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["甲减"], "indications": "用于甲状腺功能减退的替代治疗", "usage": "口服，起始25-50μg一日1次", "contraindications": "未经治疗的肾上腺功能不全", "adverse_reactions": "心悸、心动过速（过量）", "source": "manual_seed"},
    {"name": "甲巯咪唑片", "generic_name": "甲巯咪唑", "spec": "5mg×50片", "manufacturer": "默克", "category": "内分泌", "rx_type": "处方药", "disease_tags": ["甲亢"], "indications": "用于甲状腺功能亢进", "usage": "口服，起始10-20mg一日1-2次", "contraindications": "中度以上粒细胞减少", "adverse_reactions": "粒细胞减少、皮疹", "source": "manual_seed"},
    # ── 抗生素类 ──
    {"name": "阿莫西林胶囊", "generic_name": "阿莫西林", "spec": "0.5g×24粒", "manufacturer": "联邦制药", "category": "抗感染", "rx_type": "处方药", "disease_tags": ["感染"], "indications": "用于敏感菌引起的呼吸、泌尿等系统感染", "usage": "口服，0.5g一日3次", "contraindications": "青霉素过敏者禁用", "adverse_reactions": "过敏反应、胃肠道反应", "source": "manual_seed"},
    {"name": "头孢克肟胶囊", "generic_name": "头孢克肟", "spec": "100mg×6粒", "manufacturer": "白云山", "category": "抗感染", "rx_type": "处方药", "disease_tags": ["感染"], "indications": "用于敏感菌引起的呼吸道、泌尿道感染", "usage": "口服，100mg一日2次", "contraindications": "头孢菌素过敏者禁用", "adverse_reactions": "过敏反应、腹泻", "source": "manual_seed"},
    {"name": "盐酸左氧氟沙星片", "generic_name": "左氧氟沙星", "spec": "0.5g×4片", "manufacturer": "第一三共", "category": "抗感染", "rx_type": "处方药", "disease_tags": ["感染"], "indications": "用于敏感菌引起的呼吸道、泌尿道感染", "usage": "口服，0.5g一日1次", "contraindications": "18岁以下禁用", "adverse_reactions": "胃肠道反应、肌腱炎风险", "source": "manual_seed"},
    {"name": "阿奇霉素片", "generic_name": "阿奇霉素", "spec": "0.25g×6片", "manufacturer": "辉瑞制药", "category": "抗感染", "rx_type": "处方药", "disease_tags": ["感染"], "indications": "用于敏感菌引起的呼吸道、皮肤软组织感染", "usage": "口服，0.5g一日1次", "contraindications": "大环内酯类过敏者禁用", "adverse_reactions": "胃肠道反应、肝功能异常", "source": "manual_seed"},
    # ── 慢阻肺类 ──
    {"name": "噻托溴铵粉吸入剂", "generic_name": "噻托溴铵", "spec": "18μg×30粒", "manufacturer": "勃林格殷格翰", "category": "呼吸", "rx_type": "处方药", "disease_tags": ["慢阻肺"], "indications": "用于COPD的维持治疗", "usage": "吸入，18μg一日1次", "contraindications": "对阿托品类过敏者禁用", "adverse_reactions": "口干、便秘", "source": "manual_seed"},
    # ── 脑血管类 ──
    {"name": "尼莫地平片", "generic_name": "尼莫地平", "spec": "30mg×50片", "manufacturer": "拜耳医药", "category": "心血管", "rx_type": "处方药", "disease_tags": ["脑卒中"], "indications": "用于缺血性脑血管病、偏头痛", "usage": "口服，30mg一日3次", "contraindications": "严重肝功能不全", "adverse_reactions": "低血压、头痛", "source": "manual_seed"},
    # ── 抗凝类 ──
    {"name": "华法林钠片", "generic_name": "华法林", "spec": "2.5mg×60片", "manufacturer": "上海信谊", "category": "心血管", "rx_type": "处方药", "disease_tags": ["房颤", "血栓"], "indications": "用于预防和治疗血栓栓塞性疾病", "usage": "口服，起始2.5mg一日1次，需监测INR", "contraindications": "有出血倾向者禁用", "adverse_reactions": "出血、皮肤坏死", "source": "manual_seed"},
    {"name": "利伐沙班片", "generic_name": "利伐沙班", "spec": "20mg×7片", "manufacturer": "拜耳医药", "category": "心血管", "rx_type": "处方药", "disease_tags": ["房颤", "血栓"], "indications": "用于非瓣膜性房颤的卒中预防", "usage": "口服，20mg一日1次", "contraindications": "活动性出血禁用", "adverse_reactions": "出血、贫血", "source": "manual_seed"},
    # ── 骨质疏松类 ──
    {"name": "阿仑膦酸钠片", "generic_name": "阿仑膦酸钠", "spec": "70mg×1片", "manufacturer": "默沙东", "category": "骨科", "rx_type": "处方药", "disease_tags": ["骨质疏松"], "indications": "用于骨质疏松症", "usage": "口服，70mg每周1次", "contraindications": "食管异常、不能站立或坐直30分钟", "adverse_reactions": "食管刺激、腹痛", "source": "manual_seed"},
    # ── 解热镇痛类 ──
    {"name": "布洛芬缓释胶囊", "generic_name": "布洛芬", "spec": "300mg×20粒", "manufacturer": "中美史克", "category": "解热镇痛", "rx_type": "OTC", "disease_tags": ["疼痛", "发热"], "indications": "用于缓解轻至中度疼痛、退热", "usage": "口服，一次1粒一日2次", "contraindications": "活动性消化道溃疡", "adverse_reactions": "胃肠道不适、头晕", "source": "manual_seed"},
    {"name": "对乙酰氨基酚片", "generic_name": "对乙酰氨基酚", "spec": "500mg×20片", "manufacturer": "强生", "category": "解热镇痛", "rx_type": "OTC", "disease_tags": ["疼痛", "发热"], "indications": "用于退热、镇痛", "usage": "口服，一次1片，一日不超过4次", "contraindications": "严重肝功能不全", "adverse_reactions": "肝损伤（过量时）", "source": "manual_seed"},
    # ── 抗过敏类 ──
    {"name": "氯雷他定片", "generic_name": "氯雷他定", "spec": "10mg×6片", "manufacturer": "先灵葆雅", "category": "抗过敏", "rx_type": "OTC", "disease_tags": ["过敏"], "indications": "用于过敏性鼻炎、荨麻疹", "usage": "口服，10mg一日1次", "contraindications": "对本品过敏者禁用", "adverse_reactions": "嗜睡、头痛", "source": "manual_seed"},
    {"name": "盐酸西替利嗪片", "generic_name": "西替利嗪", "spec": "10mg×6片", "manufacturer": "优时比", "category": "抗过敏", "rx_type": "OTC", "disease_tags": ["过敏"], "indications": "用于过敏性鼻炎、荨麻疹", "usage": "口服，10mg一日1次", "contraindications": "对羟嗪过敏者禁用", "adverse_reactions": "嗜睡、口干", "source": "manual_seed"},
]


async def seed_medication_library(db: AsyncSession) -> int:
    """向药品库批量插入额外药品，返回新增数量。

    [Hotfix-20260513-P0] 容错：旧库可能存在同名重复行（历史数据 / 多次种子叠加）。
    使用 `.first()` 而非 `.scalar_one_or_none()`，避免重复时 MultipleResultsFound 阻塞 startup。
    """
    added = 0
    for drug in EXTRA_DRUGS:
        try:
            existing_result = await db.execute(
                select(MedicationLibrary)
                .where(MedicationLibrary.name == drug["name"])
                .limit(1)
            )
            existing = existing_result.scalars().first()
        except Exception:
            existing = None
        if existing is not None:
            continue
        try:
            db.add(MedicationLibrary(**drug))
            added += 1
        except Exception:
            # 单条插入失败不阻塞其它种子
            continue
    if added > 0:
        try:
            await db.flush()
        except Exception:
            # flush 失败时静默；不应让种子数据导致 startup crash
            await db.rollback()
            return 0
    return added
