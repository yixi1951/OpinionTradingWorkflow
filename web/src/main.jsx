import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3,
  Bell, BookOpen, Check, ChevronRight, CircleHelp, Database, Eye,
  FileText, HeartPulse, LayoutDashboard, LogOut, Menu, Plus, RefreshCw,
  Search, Server, Settings, ShieldCheck, Star, X,
} from "lucide-react";
import { api } from "./api";
import "./styles.css";

const NAV = [
  ["overview", "研究总览", LayoutDashboard],
  ["watchlist", "我的自选", Star],
  ["evidence", "舆情证据", BookOpen],
  ["account", "账户中心", Settings],
  ["system", "系统状态", HeartPulse],
];

function readQuery() {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
}

function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [page, setPage] = useState("overview");
  const [mobileNav, setMobileNav] = useState(false);
  const resetToken = useMemo(() => readQuery().get("token") || "", []);
  const isResetRoute = typeof window !== "undefined" && window.location.pathname.startsWith("/reset-password");

  useEffect(() => {
    api.me().then((r) => setUser(r.user)).catch(() => setUser(null)).finally(() => setChecking(false));
  }, []);

  if (checking) return <AppSkeleton />;
  if (isResetRoute) return <ResetPasswordScreen token={resetToken} onDone={() => { window.history.replaceState({}, "", "/"); }} />;
  if (!user) return <AuthScreen onAuthenticated={setUser} />;

  const active = NAV.find(([id]) => id === page) || NAV[0];
  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`} aria-label="主导航">
        <div className="brand"><span className="brand-mark">OC</span><span><b>OpenClaw</b><small>Research Desk</small></span></div>
        <nav>
          {NAV.map(([id, label, Icon]) => (
            <button key={id} className={page === id ? "nav-active" : ""} onClick={() => { setPage(id); setMobileNav(false); }} aria-current={page === id ? "page" : undefined}>
              <Icon size={19} /><span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note"><ShieldCheck size={18}/><p>研究辅助工具<small>所有信号均非投资建议</small></p></div>
        <button className="user-row" onClick={async () => { await api.logout(); setUser(null); }}>
          <span className="avatar">{user.username.slice(0, 1).toUpperCase()}</span><span><b>{user.username}</b><small>退出登录</small></span><LogOut size={17}/>
        </button>
      </aside>
      {mobileNav && <button className="nav-scrim" aria-label="关闭导航" onClick={() => setMobileNav(false)} />}
      <div className="workspace">
        <header className="topbar">
          <button className="icon-button menu-button" aria-label="打开导航" onClick={() => setMobileNav(true)}><Menu size={21}/></button>
          <div><h1>{active[1]}</h1><p>{page === "overview" ? "查看数据质量、市场情绪与最新研究信号" : "OpenClaw 舆情研究工作台"}</p></div>
          <div className="topbar-actions"><span className="live-status"><i/> 数据已连接</span><button className="icon-button" aria-label="通知"><Bell size={19}/></button></div>
        </header>
        <main id="main-content">
          {page === "overview" && <Overview onOpenEvidence={() => setPage("evidence")}/>}
          {page === "watchlist" && <Watchlist />}
          {page === "evidence" && <Evidence />}
          {page === "account" && <AccountCenter user={user} onUserChange={setUser} />}
          {page === "system" && <SystemStatus />}
        </main>
      </div>
    </div>
  );
}

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", password: "", email: "" });
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault(); setError(""); setInfo(""); setBusy(true);
    try {
      if (mode === "forgot") {
        await api.requestPasswordReset(form.email);
        setInfo("如果邮箱已注册，重置链接会发送到该邮箱。开发环境可查看 data/memory/email_outbox.jsonl。");
      } else {
        const r = mode === "login" ? await api.login(form.username, form.password) : await api.register(form.username, form.password, form.email);
        onAuthenticated(r.user);
      }
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return <main className="auth-layout">
    <section className="auth-brand-panel">
      <div className="brand auth-brand"><span className="brand-mark">OC</span><span><b>OpenClaw</b><small>Research Desk</small></span></div>
      <div className="auth-statement"><span className="section-label">A 股舆情研究</span><h1>看见市场情绪，<br/>也看见证据。</h1><p>聚合公开舆情、新闻和行情数据，用统一的质量口径解释每一条研究信号。</p></div>
      <div className="auth-proof"><ShieldCheck size={20}/><span><b>舆情查询平台</b><small>研究辅助，不含交易下单</small></span></div>
    </section>
    <section className="auth-form-panel">
      <form className="auth-form" onSubmit={submit}>
        <div><span className="section-label">安全访问</span><h2>{mode === "login" ? "登录研究工作台" : mode === "register" ? "创建研究账户" : "找回密码"}</h2><p>账户用于保存自选股、角色权限和阅读状态。</p></div>
        <div className="segmented" aria-label="账户操作">
          <button type="button" className={mode === "login" ? "selected" : ""} onClick={() => {setMode("login");setError("");setInfo("");}}>登录</button>
          <button type="button" className={mode === "register" ? "selected" : ""} onClick={() => {setMode("register");setError("");setInfo("");}}>注册</button>
          <button type="button" className={mode === "forgot" ? "selected" : ""} onClick={() => {setMode("forgot");setError("");setInfo("");}}>找回</button>
        </div>
        {mode !== "forgot" && <label>用户名<input required={mode !== "forgot"} minLength="3" autoComplete="username" value={form.username} onChange={(e) => setForm({...form, username:e.target.value})} placeholder="至少 3 个字符" /></label>}
        {(mode === "register" || mode === "forgot") && <label>邮箱{mode === "forgot" ? "" : "（可选）"}<input type="email" required={mode === "forgot"} autoComplete="email" value={form.email} onChange={(e) => setForm({...form, email:e.target.value})} placeholder="用于验证与重置" /></label>}
        {mode !== "forgot" && <label>密码<input required minLength="8" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={form.password} onChange={(e) => setForm({...form, password:e.target.value})} placeholder="至少 8 个字符" aria-describedby={error ? "auth-error" : undefined}/></label>}
        {error && <div className="inline-error" id="auth-error" role="alert"><AlertTriangle size={17}/>{error}</div>}
        {info && <div className="inline-info" role="status">{info}</div>}
        <button className="primary-button" disabled={busy}>{busy && <RefreshCw className="spin" size={17}/>} {busy ? "正在处理" : mode === "login" ? "登录工作台" : mode === "register" ? "创建并登录" : "发送重置链接"}<ChevronRight size={18}/></button>
        <p className="legal-copy">继续即表示你理解：本产品仅提供数据统计与研究辅助，不构成投资建议。</p>
      </form>
    </section>
  </main>;
}

function ResetPasswordScreen({ token, onDone }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await api.confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return <main className="auth-layout"><section className="auth-form-panel" style={{margin:"auto"}}>
    <form className="auth-form" onSubmit={submit}>
      <div><span className="section-label">账户安全</span><h2>设置新密码</h2><p>链接使用一次后立即失效，并会清除既有登录会话。</p></div>
      {!token && <div className="inline-error" role="alert"><AlertTriangle size={17}/>缺少重置令牌</div>}
      {done ? <div className="inline-info" role="status">密码已更新。<button type="button" className="text-button" onClick={onDone}>返回登录</button></div> : <>
        <label>新密码<input required minLength="8" type="password" autoComplete="new-password" value={password} onChange={(e)=>setPassword(e.target.value)} /></label>
        {error && <div className="inline-error" role="alert"><AlertTriangle size={17}/>{error}</div>}
        <button className="primary-button" disabled={busy || !token}>{busy ? "提交中" : "确认重置"}</button>
      </>}
    </form>
  </section></main>;
}

function AccountCenter({ user, onUserChange }) {
  const isAdmin = (user.roles || []).includes("admin");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [users, setUsers] = useState([]);
  const reloadMe = () => api.me().then((r) => onUserChange(r.user));
  useEffect(() => {
    if (isAdmin) api.adminUsers().then((r) => setUsers(r.users || [])).catch(() => setUsers([]));
  }, [isAdmin]);
  return <div className="page-stack">
    <section className="status-strip">
      <div><span className={`status-icon ${user.email_verified ? "good" : "warn"}`}>{user.email_verified ? <Check/> : <AlertTriangle/>}</span>
        <p><b>{user.username}</b><small>角色：{(user.roles || []).join("、") || "viewer"} · 邮箱：{user.email || "未绑定"}{user.email_verified ? "（已验证）" : "（未验证）"}</small></p>
      </div>
      {!user.email_verified && user.email && <button className="text-button" onClick={async () => { setErr(""); try { await api.resendVerification(); setMsg("验证邮件已发送"); await reloadMe(); } catch (e) { setErr(e.message); } }}>重发验证邮件</button>}
    </section>
    {msg && <div className="inline-info" role="status">{msg}</div>}
    {err && <div className="inline-error" role="alert"><AlertTriangle size={17}/>{err}</div>}
    <section className="operating-boundary"><ShieldCheck size={23}/><div><h2>产品边界</h2><p>本平台仅提供舆情查询与研究辅助，不含下单、券商对接或实盘交易能力。所有信号均非投资建议。</p></div></section>
    {isAdmin && <section>
      <SectionHeader title="用户与角色" subtitle="admin 可调整角色：viewer / analyst / admin"/>
      <div className="watch-table" role="table"><div className="table-head" role="row"><span>用户</span><span>邮箱</span><span>角色</span><span>操作</span></div>
        {users.map((u) => <div className="table-row" role="row" key={u.id}>
          <span><b>{u.username}</b></span><span>{u.email || "—"}</span><span>{(u.roles || []).join(", ")}</span>
          <span><button className="text-button" onClick={async () => {
            const next = window.prompt("输入角色，逗号分隔", (u.roles || []).join(","));
            if (!next) return;
            const roles = next.split(",").map((x) => x.trim()).filter(Boolean);
            await api.updateRoles(u.id, roles);
            const listed = await api.adminUsers();
            setUsers(listed.users || []);
          }}>改角色</button></span>
        </div>)}
      </div>
    </section>}
  </div>;
}

function Overview({ onOpenEvidence }) {
  const { data, loading, error, reload } = useDashboard();
  if (loading) return <DashboardSkeleton/>;
  if (error) return <ErrorState message={error} onRetry={reload}/>;
  const quality = data.quality || {};
  return <div className="page-stack">
    <section className="status-strip"><div><span className={`status-icon ${quality.status === "PASS" ? "good" : "warn"}`}>{quality.status === "PASS" ? <Check/> : <AlertTriangle/>}</span><p><b>{quality.status === "PASS" ? "数据质量可用于研究" : "本期数据存在质量风险"}</b><small>{quality.message}</small></p></div><button className="text-button" onClick={reload}><RefreshCw size={16}/>刷新数据</button></section>
    <section className="metric-band" aria-label="核心指标">
      <Metric label="覆盖标的" value={data.summary.symbols} suffix="只" note="当前研究池" />
      <Metric label="有效样本" value={data.summary.samples} suffix="条" note={`${data.summary.platforms} 个来源`} />
      <Metric label="用户观点占比" value={data.summary.comment_share} suffix="%" note="其余含新闻与研报" tone={data.summary.comment_share < 20 ? "warn" : ""}/>
      <Metric label="样本外准确率" value={data.evaluation.accuracy} suffix="%" note={`Sharpe-like ${data.evaluation.sharpe}`} tone="danger"/>
    </section>
    <section className="research-grid">
      <div className="research-main">
        <SectionHeader title="最新研究信号" subtitle="按综合舆情分排序，低样本标的已标记" action={<button className="text-button" onClick={onOpenEvidence}>查看证据 <ChevronRight size={16}/></button>}/>
        <div className="signal-list">{data.picks.map((pick, i) => <SignalRow key={pick.symbol} pick={pick} rank={i+1}/>)}</div>
      </div>
      <aside className="quality-panel">
        <SectionHeader title="数据构成" subtitle="用于判断结论可信度" />
        <CompositionRow label="新闻与公告" value={data.summary.news_share} color="blue"/>
        <CompositionRow label="用户观点" value={data.summary.comment_share} color="green"/>
        <CompositionRow label="噪声与回退" value={data.summary.noise_share} color="amber"/>
        <div className="quality-callout"><CircleHelp size={18}/><p><b>为什么这很重要</b><span>新闻占比过高时，榜单更接近资讯情绪，不等同于投资者观点。</span></p></div>
      </aside>
    </section>
    <section className="trend-section"><SectionHeader title="市场情绪脉络" subtitle="最近采集日按标的聚合，0 为中性"/><SentimentBars items={data.picks.slice(0,8)}/></section>
  </div>;
}

function Watchlist() {
  const { data, loading, error, reload } = useDashboard();
  const [symbol, setSymbol] = useState(""); const [actionError, setActionError] = useState("");
  if (loading) return <DashboardSkeleton/>; if (error) return <ErrorState message={error} onRetry={reload}/>;
  const picks = new Map(data.picks.map(p => [p.symbol,p]));
  const add = async (e) => { e.preventDefault(); setActionError(""); try { await api.addWatch(symbol); setSymbol(""); reload(); } catch(e){setActionError(e.message);} };
  return <div className="page-stack"><section className="toolbar-band"><form onSubmit={add} className="symbol-form"><label htmlFor="symbol">添加股票代码</label><div><Search size={18}/><input id="symbol" value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} placeholder="例如 600519.SH"/><button className="primary-button compact"><Plus size={17}/>添加自选</button></div>{actionError && <small className="field-error">{actionError}</small>}</form></section>
    <section><SectionHeader title="我的自选股" subtitle={`${data.watchlist.length} 只标的，数据来自最近一次成功采集`}/>{data.watchlist.length ? <div className="watch-table" role="table"><div className="table-head" role="row"><span>标的</span><span>综合情绪</span><span>样本</span><span>主要来源</span><span>操作</span></div>{data.watchlist.map(sym=><WatchRow key={sym} symbol={sym} pick={picks.get(sym)} onRemove={async()=>{await api.removeWatch(sym);reload();}}/>)}</div>:<EmptyState icon={Star} title="还没有自选股" body="添加你真正关心的标的，后续预警和证据会围绕自选股组织。"/>}</section></div>;
}

function Evidence() {
  const { data, loading, error } = useDashboard(); const [symbol,setSymbol]=useState(""); const [evidence,setEvidence]=useState(null); const [busy,setBusy]=useState(false); const [loadError,setLoadError]=useState("");
  useEffect(()=>{ if(data?.picks?.length && !symbol) setSymbol(data.picks[0].symbol); },[data,symbol]);
  useEffect(()=>{ if(!symbol)return;setBusy(true);setLoadError("");api.evidence(symbol).then(setEvidence).catch(e=>setLoadError(e.message)).finally(()=>setBusy(false));},[symbol]);
  if(loading)return <DashboardSkeleton/>; if(error)return <ErrorState message={error}/>;
  return <div className="page-stack"><section className="toolbar-band evidence-toolbar"><div><label htmlFor="evidence-symbol">研究标的</label><select id="evidence-symbol" value={symbol} onChange={e=>setSymbol(e.target.value)}>{data.picks.map(p=><option key={p.symbol}>{p.symbol}</option>)}</select></div><p><Eye size={18}/>原文按情绪强度与来源质量排序，点击来源可核对上下文。</p></section>
  {busy ? <EvidenceSkeleton/> : loadError ? <ErrorState message={loadError}/> : evidence && <><section className="evidence-summary"><div><span className={`direction-badge ${evidence.score >= 0 ? "positive":"negative"}`}>{evidence.score >= 0 ? <ArrowUpRight/>:<ArrowDownRight/>}{evidence.score >= 0 ? "偏多":"偏空"}</span><h2>{evidence.symbol}</h2><p>{evidence.summary}</p></div><div className="evidence-stats"><Metric label="综合情绪" value={evidence.score.toFixed(3)}/><Metric label="有效证据" value={evidence.items.length} suffix="条"/></div></section><section><SectionHeader title="原始证据" subtitle="观点与新闻分开标记，避免把资讯转载误判成用户共识"/><div className="evidence-list">{evidence.items.map((item,i)=><EvidenceItem key={`${item.url}-${i}`} item={item}/>)}</div></section></>}
  </div>;
}

function SystemStatus(){const [data,setData]=useState(null);const [error,setError]=useState("");const load=()=>api.status().then(setData).catch(e=>setError(e.message));useEffect(load,[]);return <div className="page-stack"><section><SectionHeader title="服务健康" subtitle="内部服务仅通过 API 网关访问" action={<button className="text-button" onClick={load}><RefreshCw size={16}/>重新检查</button>}/>{error?<ErrorState message={error}/>:!data?<DashboardSkeleton/>:<div className="service-list">{Object.entries(data).map(([name,value])=><div className="service-row" key={name}><span className={`service-icon ${value === "ok" || value?.status === "ok" ? "online":"offline"}`}><Server size={18}/></span><p><b>{serviceName(name)}</b><small>{typeof value === "string" ? "API 网关" : value?.status === "down" ? "暂时不可用" : "运行正常"}</small></p><span className="service-state">{value === "ok" || value?.status === "ok" ? "正常":"降级"}</span></div>)}</div>}</section><section className="operating-boundary"><ShieldCheck size={23}/><div><h2>当前运行边界</h2><p>本平台面向舆情查询与研究辅助，不含交易下单。任何数据不足、服务降级或质量门禁失败都应降低结论置信度。</p></div></section></div>}

function useDashboard(){const [data,setData]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState("");const reload=()=>{setLoading(true);setError("");api.dashboard().then(setData).catch(e=>setError(e.message)).finally(()=>setLoading(false));};useEffect(reload,[]);return{data,loading,error,reload};}
function Metric({label,value,suffix="",note,tone=""}){return <div className={`metric ${tone}`}><span>{label}</span><strong>{value}<em>{suffix}</em></strong>{note&&<small>{note}</small>}</div>}
function SectionHeader({title,subtitle,action}){return <div className="section-header"><div><h2>{title}</h2><p>{subtitle}</p></div>{action}</div>}
function SignalRow({pick,rank}){const positive=pick.score>=0;return <article className="signal-row"><span className="rank">{String(rank).padStart(2,"0")}</span><div className="symbol"><b>{pick.symbol}</b><small>{pick.samples<20?"样本偏少":"样本充足"}</small></div><div className={`score ${positive?"positive":"negative"}`}>{positive?<ArrowUpRight/>:<ArrowDownRight/>}<b>{positive?"+":""}{pick.score.toFixed(3)}</b></div><div className="source-tags">{pick.platforms.slice(0,3).map(p=><span key={p.name}>{platformName(p.name)} {p.score>=0?"+":""}{p.score.toFixed(2)}</span>)}</div><div className="sample-count"><b>{pick.samples}</b><small>样本</small></div></article>}
function CompositionRow({label,value,color}){return <div className="composition-row"><div><span><i className={color}/>{label}</span><b>{value}%</b></div><div className="bar-track"><i className={color} style={{width:`${Math.min(value,100)}%`}}/></div></div>}
function SentimentBars({items}){const max=Math.max(...items.map(x=>Math.abs(x.score)),.1);return <div className="sentiment-bars">{items.map(x=><div key={x.symbol}><span>{x.symbol}</span><div className="axis"><i className={x.score>=0?"pos":"neg"} style={x.score>=0?{left:"50%",width:`${Math.abs(x.score)/max*48}%`}:{right:"50%",width:`${Math.abs(x.score)/max*48}%`}}/></div><b className={x.score>=0?"positive":"negative"}>{x.score>=0?"+":""}{x.score.toFixed(3)}</b></div>)}</div>}
function WatchRow({symbol,pick,onRemove}){return <div className="table-row" role="row"><span className="symbol"><b>{symbol}</b><small>{pick?"最近有数据":"等待采集"}</small></span><span className={pick?.score>=0?"positive":"negative"}>{pick?`${pick.score>=0?"+":""}${pick.score.toFixed(3)}`:"暂无"}</span><span>{pick?.samples??0}</span><span>{pick?.platforms?.slice(0,2).map(p=>platformName(p.name)).join("、")||"暂无"}</span><button className="icon-button" aria-label={`移除 ${symbol}`} onClick={onRemove}><X size={17}/></button></div>}
function EvidenceItem({item}){return <article className="evidence-item"><div className="evidence-meta"><span className={`content-type ${item.kind === "comment"?"comment":"news"}`}>{item.kind === "comment"?"用户观点":"新闻资料"}</span><span>{platformName(item.platform)}</span><time>{item.post_time||"时间未知"}</time><span className={item.score>=0?"positive":"negative"}>{item.score>=0?"+":""}{item.score.toFixed(2)}</span></div><h3>{item.title||"未命名内容"}</h3><p>{item.content}</p>{item.url&&<a href={item.url} target="_blank" rel="noreferrer">查看原始来源 <ChevronRight size={15}/></a>}</article>}
function EmptyState({icon:Icon,title,body}){return <div className="empty-state"><Icon/><h3>{title}</h3><p>{body}</p></div>}
function ErrorState({message,onRetry}){return <div className="empty-state error-state"><AlertTriangle/><h3>暂时无法载入</h3><p>{message}</p>{onRetry&&<button className="secondary-button" onClick={onRetry}><RefreshCw size={16}/>重试</button>}</div>}
function AppSkeleton(){return <div className="app-skeleton"><div/><main><i/><i/><i/></main></div>}
function DashboardSkeleton(){return <div className="dashboard-skeleton"><i/><div><i/><i/><i/><i/></div><i/></div>}
function EvidenceSkeleton(){return <div className="evidence-skeleton"><i/><i/><i/></div>}
function serviceName(n){return ({api:"API 网关",collector:"数据采集",inference:"情绪推理",compute:"策略计算"})[n]||n}
function platformName(n){return ({sina_finance:"新浪财经",eastmoney:"东方财富",guba:"股吧",weibo:"微博",xueqiu:"雪球",douyin:"抖音"})[n]||n}

createRoot(document.getElementById("root")).render(<React.StrictMode><App/></React.StrictMode>);
