'use client';

export default function PrivacyPolicyPage() {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#ffffff',
        padding: '24px 20px 40px',
        color: '#1F2937',
        fontSize: 14,
        lineHeight: 1.8,
      }}
    >
      <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 16px' }}>隐私政策</h1>
      <p style={{ color: '#6B7280', marginBottom: 16 }}>
        生效日期：2026-05-07 ｜ 版本号：v1.0
      </p>

      <p>
        「宾尼小康 AI 健康管家」（以下简称"我们"）尊重并保护用户的个人信息和隐私。
        本政策详细说明我们如何收集、使用、存储和保护您的个人信息。请您仔细阅读。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>一、我们收集的信息</h2>
      <p>
        1.1 <strong>账号信息</strong>：当您注册或登录时，我们会收集您的手机号码用于发送短信验证码以及创建账号。
        <br />
        1.2 <strong>设备信息</strong>：我们会收集设备型号、操作系统版本、网络状态等技术信息，用于服务安全和性能优化。
        <br />
        1.3 <strong>健康信息</strong>：基于您的主动填写或上传，我们会收集您的健康档案、报告解读、问诊记录等健康相关信息。
        <br />
        1.4 <strong>使用日志</strong>：我们会记录您使用本服务的访问日志、操作行为、停留时长等信息，用于服务改进。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>二、我们如何使用信息</h2>
      <p>
        2.1 提供、维护、改进我们的服务；
        <br />
        2.2 根据您的健康档案为您生成个性化健康建议；
        <br />
        2.3 在您授权的范围内向您推送服务通知或营销信息；
        <br />
        2.4 防范欺诈、保障您的账号和资金安全；
        <br />
        2.5 满足法律法规要求或配合行政、司法机关调查。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>三、信息的存储与保护</h2>
      <p>
        3.1 您的信息将存储于中华人民共和国境内的合规云服务器；
        <br />
        3.2 我们采用加密传输（HTTPS）、加密存储、最小权限访问控制等多重技术手段保护您的信息；
        <br />
        3.3 我们仅在实现服务目的所必需的最短期间内保留您的信息。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>四、信息的共享、转让和披露</h2>
      <p>
        除以下情形外，我们不会向第三方共享、转让或披露您的个人信息：
        <br />
        4.1 取得您的明确同意；
        <br />
        4.2 法律法规要求或政府主管部门强制要求；
        <br />
        4.3 为维护本服务及其他用户的合法权益所必需。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>五、您的权利</h2>
      <p>
        5.1 您有权查询、更正您的个人信息；
        <br />
        5.2 您有权撤回您此前给予的授权同意；
        <br />
        5.3 您有权申请注销账号；
        <br />
        5.4 您可联系我们客服行使上述权利，我们将在收到请求后 15 个工作日内予以答复。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>六、儿童信息保护</h2>
      <p>
        本服务主要面向 18 周岁以上的成年用户。
        如您是未成年人的监护人，请您指导未成年人在监护下使用本服务，并由监护人代为同意本政策。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>七、政策更新与联系方式</h2>
      <p>
        本政策可能随业务需要进行更新。当政策发生重大变更时，我们将以适当方式通知您，请您留意。
        如您对本政策有任何疑问，可通过应用内客服与我们联系。
      </p>

      <p style={{ marginTop: 32, color: '#9CA3AF', fontSize: 12 }}>
        — 本政策自您勾选同意之时起对您生效 —
      </p>
    </div>
  );
}
