import { Link } from 'react-router-dom'

const colors = [
  ['品牌绿', '#1D9E75', '主要操作与关键状态'],
  ['深品牌绿', '#0F6E56', '悬停与强调'],
  ['浅品牌绿', '#E1F5EE', '选中与辅助背景'],
  ['页面背景', '#F0F4F8', '后台工作区'],
  ['危险红', '#DC2626', '高风险与失败'],
  ['提醒黄', '#D97706', '待确认与警告'],
]

export default function DesignSystem() {
  return (
    <main className="ds-page">
      <header className="ds-hero">
        <div>
          <p className="ds-eyebrow">XIAOYUN DESIGN SYSTEM</p>
          <h1>小云智服界面规范</h1>
          <p>统一买家端、坐席工作台与效果看板的颜色、组件和交互状态。</p>
        </div>
        <nav className="ds-nav" aria-label="演示入口">
          <Link className="ds-btn ds-btn-secondary" to="/chat">买家端</Link>
          <Link className="ds-btn ds-btn-primary" to="/login">坐席端</Link>
        </nav>
      </header>

      <section className="ds-section" aria-labelledby="colors-title">
        <div className="ds-section-heading">
          <span>01</span><div><h2 id="colors-title">颜色与语义</h2><p>颜色服务于信息层级，不用颜色装饰业务。</p></div>
        </div>
        <div className="ds-color-grid">
          {colors.map(([name, hex, usage]) => (
            <article className="ds-color-card" key={hex}>
              <div className="ds-swatch" style={{ background: hex }} aria-label={`${name} ${hex}`} />
              <div><strong>{name}</strong><code>{hex}</code><p>{usage}</p></div>
            </article>
          ))}
        </div>
      </section>

      <section className="ds-section" aria-labelledby="components-title">
        <div className="ds-section-heading">
          <span>02</span><div><h2 id="components-title">核心组件</h2><p>覆盖演示链路中的操作、状态与输入。</p></div>
        </div>
        <div className="ds-demo-grid">
          <article className="ds-card">
            <h3>按钮</h3>
            <div className="ds-row">
              <button className="ds-btn ds-btn-primary">运行评测</button>
              <button className="ds-btn ds-btn-secondary">查看详情</button>
              <button className="ds-btn ds-btn-danger">转人工</button>
            </div>
          </article>
          <article className="ds-card">
            <h3>业务状态</h3>
            <div className="ds-row">
              <span className="ds-badge ds-badge-success">AI 已回答</span>
              <span className="ds-badge ds-badge-warning">待买家确认</span>
              <span className="ds-badge ds-badge-danger">等待人工</span>
            </div>
          </article>
          <article className="ds-card">
            <h3>输入框</h3>
            <label className="ds-label" htmlFor="demo-question">买家问题</label>
            <input id="demo-question" className="ds-input" value="这件衣服可以换货吗？" readOnly />
          </article>
          <article className="ds-card ds-stat-card">
            <p>转人工判断准确率</p>
            <strong>以线上评测为准</strong>
            <small>不在静态规范页伪造结果</small>
          </article>
        </div>
      </section>

      <section className="ds-section" aria-labelledby="rules-title">
        <div className="ds-section-heading">
          <span>03</span><div><h2 id="rules-title">使用原则</h2><p>让 AI 协作改界面时也保持一致。</p></div>
        </div>
        <div className="ds-rule-grid">
          <article><strong>复用优先</strong><p>先复用现有组件与状态，再新增样式。</p></article>
          <article><strong>安全可见</strong><p>转人工、待确认和演示数据必须明确标识。</p></article>
          <article><strong>结果可核验</strong><p>动态指标只从效果看板读取，不写死在页面中。</p></article>
        </div>
      </section>
    </main>
  )
}
