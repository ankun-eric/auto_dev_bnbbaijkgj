'use client';

export default function ServiceAgreementPage() {
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
      <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 16px' }}>用户服务协议</h1>
      <p style={{ color: '#6B7280', marginBottom: 16 }}>
        生效日期：2026-05-07 ｜ 版本号：v1.0
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>一、协议说明</h2>
      <p>
        欢迎使用「宾尼小康 AI 健康管家」（以下简称"本服务"）。本协议是您与本服务运营方就使用本服务所订立的协议。
        在您注册并使用本服务前，请您仔细阅读本协议的全部内容，特别是字体加粗或下划线的条款。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>二、账号注册与登录</h2>
      <p>
        2.1 您在使用本服务前需通过手机号 + 短信验证码方式完成账号登录或注册。
        <br />
        2.2 您应当确保所提供的手机号信息真实、准确、完整，因信息错误造成的后果由您自行承担。
        <br />
        2.3 您应妥善保管账号信息，因您主动泄露或保管不善导致的损失由您自行承担。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>三、服务内容</h2>
      <p>
        本服务为您提供 AI 健康咨询、健康档案管理、健康计划生成、个性化健康建议等功能。
        本服务所提供的健康建议仅供参考，不能替代专业医疗机构的诊疗意见。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>四、用户行为规范</h2>
      <p>
        4.1 您承诺遵守中华人民共和国相关法律法规，不利用本服务从事任何违法违规活动。
        <br />
        4.2 您不得对本服务进行任何形式的反向工程、反编译、破解或非法访问。
        <br />
        4.3 您不得发布违法、淫秽、暴力、虚假及侵犯他人合法权益的内容。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>五、知识产权</h2>
      <p>本服务所涉及的所有内容（包括但不限于文字、图标、UI 设计、算法模型）均归运营方或合法权利人所有。</p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>六、服务变更与终止</h2>
      <p>
        6.1 运营方有权根据业务需要变更、暂停或终止本服务，并将以适当方式通知您。
        <br />
        6.2 您可随时停止使用本服务，并可申请注销账号。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>七、免责声明</h2>
      <p>
        7.1 因不可抗力或运营方不能控制的原因导致服务中断或您的损失，运营方不承担责任。
        <br />
        7.2 本服务提供的健康建议仅供参考，您应在专业医生指导下进行健康决策。
      </p>

      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '20px 0 8px' }}>八、协议变更与争议解决</h2>
      <p>
        本协议条款如有变更，运营方将以适当方式通知您。如您对本协议或本服务存在争议，
        应优先通过友好协商解决；协商不成的，可向运营方所在地有管辖权的人民法院提起诉讼。
      </p>

      <p style={{ marginTop: 32, color: '#9CA3AF', fontSize: 12 }}>
        — 本协议自您勾选同意之时起对您生效 —
      </p>
    </div>
  );
}
