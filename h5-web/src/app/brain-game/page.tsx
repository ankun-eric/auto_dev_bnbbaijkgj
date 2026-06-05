'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import api from '@/lib/api';
import './page.css';

// ========== 类型定义 ==========
type Difficulty = 'basic' | 'mid' | 'hard';
type PageView = 'home' | 'math-difficulty' | 'math-game' | 'math-result' | 'ranking' | 'team' | 'team-game' | 'team-result';
type RankTab = 'street' | 'district' | 'city';

interface UserInfo {
  user_id: number;
  nickname: string;
  avatar: string;
  phone: string;
}

interface RegionItem {
  adcode: string;
  name: string;
  level: string;
  center?: string;
}

interface RegionTree {
  adcode: string;
  name: string;
  level: string;
  children: RegionTree[];
}

interface MyLoc {
  province: string;
  city: string;
  district: string;
  street: string;
}

interface Question {
  text: string;
  ans: number;
  options: number[];
}

interface ScoreResult {
  id: number;
  score: number;
  right_count: number;
  time_seconds: number;
  difficulty: string;
  street_rank: number | null;
  district_rank: number | null;
  city_rank: number | null;
}

interface RankItem {
  rank: number;
  user_id: number;
  nickname: string;
  avatar: string | null;
  score: number;
  time_seconds: number;
  is_me: boolean;
}

interface ChallengeItem {
  id: number;
  code: string;
  difficulty: string;
  difficulty_name: string;
  team_size: number;
  status: string;
  total_score: number | null;
  member_count: number;
  done_count: number;
  created_at: string;
  expires_at: string | null;
}

interface ChallengeDetail {
  id: number;
  code: string;
  difficulty: string;
  team_size: number;
  status: string;
  total_score: number | null;
  created_at: string;
  expires_at: string | null;
  members: {
    user_id: number;
    nickname: string;
    avatar: string | null;
    score: number;
    right_count: number;
    time_seconds: number;
    done: boolean;
  }[];
}

// ========== 难度配置 ==========
const DIFF_CONFIG: Record<Difficulty, { time: number; name: string; label: string; rule: string; emoji: string }> = {
  basic: { time: 180, name: '基础训练', label: '基础训练', rule: '1～9以内 加减法（3个1位数）', emoji: '🌱' },
  mid: { time: 300, name: '进阶训练', label: '进阶训练', rule: '1～9以内 加减乘（3个1位数）', emoji: '🌳' },
  hard: { time: 600, name: '挑战训练', label: '挑战训练', rule: '10～99以内 加减法（3个两位数）', emoji: '🔥' },
};

// ========== 辅助函数 ==========
function rand(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function genQuestion(diff: Difficulty): Question {
  let a: number, b: number, c: number, op1: string, op2: string, ans: number, text: string;
  if (diff === 'basic') {
    a = rand(1, 9); b = rand(1, 9); c = rand(1, 9);
    op1 = ['+', '-'][rand(0, 1)]; op2 = ['+', '-'][rand(0, 1)];
    ans = eval(`${a}${op1}${b}${op2}${c}`);
    text = `${a} ${op1} ${b} ${op2} ${c}`;
  } else if (diff === 'mid') {
    a = rand(1, 9); b = rand(1, 9); c = rand(1, 9);
    op1 = ['+', '-', '×'][rand(0, 2)]; op2 = ['+', '-', '×'][rand(0, 2)];
    const e1 = op1 === '×' ? '*' : op1;
    const e2 = op2 === '×' ? '*' : op2;
    ans = eval(`${a}${e1}${b}${e2}${c}`);
    text = `${a} ${op1} ${b} ${op2} ${c}`;
  } else {
    a = rand(10, 99); b = rand(10, 99); c = rand(10, 99);
    op1 = ['+', '-'][rand(0, 1)]; op2 = ['+', '-'][rand(0, 1)];
    ans = eval(`${a}${op1}${b}${op2}${c}`);
    text = `${a} ${op1} ${b} ${op2} ${c}`;
  }
  const opts = new Set([ans]);
  while (opts.size < 4) {
    const offset = rand(-5, 5);
    if (offset !== 0) opts.add(ans + offset);
  }
  const optArr = Array.from(opts).sort(() => Math.random() - 0.5);
  return { text, ans, options: optArr };
}

function formatTimer(seconds: number): string {
  const m = String(Math.floor(seconds / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return `${m}:${s}`;
}

// ========== 主组件 ==========
export default function BrainGamePage() {
  // 用户信息
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);

  // 页面视图
  const [view, setView] = useState<PageView>('home');
  const [prevView, setPrevView] = useState<PageView>('home');

  // 位置信息
  const [myLoc, setMyLoc] = useState<MyLoc>(() => {
    if (typeof window === 'undefined') return { province: '', city: '', district: '', street: '' };
    try {
      return JSON.parse(localStorage.getItem('brainMyLoc') || '{}');
    } catch { return { province: '', city: '', district: '', street: '' }; }
  });

  // 数学游戏状态
  const [difficulty, setDifficulty] = useState<Difficulty>('basic');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [score, setScore] = useState(0);
  const [rightCount, setRightCount] = useState(0);
  const [timeLeft, setTimeLeft] = useState(180);
  const [startTime, setStartTime] = useState(0);
  const [gameOver, setGameOver] = useState(false);
  const [answered, setAnswered] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const scoreRef = useRef(0);
  const rightRef = useRef(0);

  // 答题结果
  const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);

  // 排行榜
  const [rankTab, setRankTab] = useState<RankTab>('street');
  const [rankList, setRankList] = useState<RankItem[]>([]);
  const [myRanks, setMyRanks] = useState<{ street: number | null; district: number | null; city: number | null }>({
    street: null, district: null, city: null,
  });
  const [rankTotal, setRankTotal] = useState(0);

  // 地区选择器
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerSel, setPickerSel] = useState<MyLoc>({ province: '', city: '', district: '', street: '' });
  const [regionTree, setRegionTree] = useState<RegionTree[]>([]);

  // 组队挑战
  const [activeChallenges, setActiveChallenges] = useState<ChallengeItem[]>([]);
  const [historyChallenges, setHistoryChallenges] = useState<ChallengeItem[]>([]);
  const [teamDiff, setTeamDiff] = useState<Difficulty>('basic');
  const [teamSize, setTeamSize] = useState(4);
  const [challengeDetail, setChallengeDetail] = useState<ChallengeDetail | null>(null);

  // 组队答题
  const [teamQuestions, setTeamQuestions] = useState<Question[]>([]);
  const [teamCurrentQ, setTeamCurrentQ] = useState(0);
  const [teamScore, setTeamScore] = useState(0);
  const [teamRightCount, setTeamRightCount] = useState(0);
  const [teamTimeLeft, setTeamTimeLeft] = useState(180);
  const [teamStartTime, setTeamStartTime] = useState(0);
  const [teamGameOver, setTeamGameOver] = useState(false);
  const [teamAnswered, setTeamAnswered] = useState(false);
  const teamTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const teamScoreRef = useRef(0);
  const teamRightRef = useRef(0);
  const [currentChallengeId, setCurrentChallengeId] = useState<number | null>(null);

  // 分享弹窗
  const [shareOpen, setShareOpen] = useState(false);

  // ========== 初始化：加载用户信息 ==========
  useEffect(() => {
    const loadUser = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await api.get('/api/brain-game/user-info');
        setUserInfo(res.data || res);
      } catch {
        const saved = localStorage.getItem('user');
        if (saved) {
          try {
            const u = JSON.parse(saved);
            setUserInfo({
              user_id: u.id,
              nickname: u.nickname || '用户',
              avatar: u.avatar || '',
              phone: u.phone || '',
            });
          } catch { /* ignore */ }
        }
      }
    };
    loadUser();
    loadRegionTree();
  }, []);

  // ========== 加载行政区划树 ==========
  const loadRegionTree = async () => {
    try {
      const res = await api.get('/api/brain-game/regions/tree');
      const tree = res.data?.tree || res?.tree || [];
      setRegionTree(tree);
    } catch { /* use empty */ }
  };

  // ========== 导航 ==========
  const navigate = (v: PageView) => {
    setPrevView(view);
    setView(v);
    window.scrollTo(0, 0);
  };

  // ========== 启动数学游戏 ==========
  const startGame = (diff: Difficulty) => {
    setDifficulty(diff);
    setCurrentQ(0);
    setScore(0);
    setRightCount(0);
    scoreRef.current = 0;
    rightRef.current = 0;
    setTimeLeft(DIFF_CONFIG[diff].time);
    setStartTime(Date.now());
    setGameOver(false);
    setAnswered(false);
    setScoreResult(null);
    const qs: Question[] = [];
    for (let i = 0; i < 10; i++) qs.push(genQuestion(diff));
    setQuestions(qs);
    navigate('math-game');
    startTimer(DIFF_CONFIG[diff].time);
  };

  const startTimer = (total: number) => {
    clearInterval(timerRef.current!);
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          finishGame();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const answerQuestion = (val: number) => {
    if (answered) return;
    setAnswered(true);
    const q = questions[currentQ];
    const correct = val === q.ans;
    if (correct) {
      const newScore = scoreRef.current + 10;
      const newRight = rightRef.current + 1;
      scoreRef.current = newScore;
      rightRef.current = newRight;
      setScore(newScore);
      setRightCount(newRight);
    }
    setTimeout(() => {
      if (currentQ >= 9) {
        finishGame();
      } else {
        setCurrentQ(c => c + 1);
        setAnswered(false);
      }
    }, 600);
  };

  const finishGame = () => {
    clearInterval(timerRef.current!);
    setGameOver(true);
    const used = Math.min(
      Math.floor((Date.now() - startTime) / 1000),
      DIFF_CONFIG[difficulty].time
    );
    submitAndShowResult(used);
  };

  const submitAndShowResult = async (usedSeconds: number) => {
    const finalScore = scoreRef.current;
    const finalRight = rightRef.current;
    try {
      const body = {
        difficulty,
        score: finalScore,
        right_count: finalRight,
        total_count: 10,
        time_seconds: usedSeconds,
        province: myLoc.province || undefined,
        city: myLoc.city || undefined,
        district: myLoc.district || undefined,
        street: myLoc.street || undefined,
      };
      
      const res = await api.post('/api/brain-game/scores', body);
      const result = res.data || res;
      setScoreResult(result);
    } catch {
      // Fallback: local only
      setScoreResult({
        id: 0,
        score: finalScore,
        right_count: finalRight,
        time_seconds: usedSeconds,
        difficulty,
        street_rank: null,
        district_rank: null,
        city_rank: null,
      });
    }
    navigate('math-result');
  };

  // ========== 排行榜 ==========
  const loadRankings = useCallback(async (tab: RankTab) => {
    try {
      const region = tab === 'street' ? myLoc.street : tab === 'district' ? myLoc.district : myLoc.city;
      const res = await api.get('/api/brain-game/rankings', { params: { tab, region: region || undefined } });
      const data = res.data || res;
      setRankList(data.list || []);
      setRankTotal(data.total || 0);
      setMyRanks(prev => ({ ...prev, [tab]: data.my_rank || null }));
    } catch { /* ignore */ }
  }, [myLoc]);

  useEffect(() => {
    if (view === 'ranking') {
      loadRankings(rankTab);
    }
  }, [view, rankTab, loadRankings]);

  // ========== 地区选择器 ==========
  const openPicker = () => {
    setPickerSel({ ...myLoc });
    setPickerOpen(true);
  };
  const closePicker = () => setPickerOpen(false);

  const selectPickerItem = (level: keyof MyLoc, name: string) => {
    const order: (keyof MyLoc)[] = ['province', 'city', 'district', 'street'];
    const idx = order.indexOf(level);
    const newSel = { ...pickerSel, [level]: name };
    for (let i = idx + 1; i < order.length; i++) {
      newSel[order[i]] = '';
    }
    setPickerSel(newSel);
  };

  const confirmPicker = () => {
    if (!pickerSel.province || !pickerSel.city || !pickerSel.district || !pickerSel.street) return;
    setMyLoc(pickerSel);
    localStorage.setItem('brainMyLoc', JSON.stringify(pickerSel));
    setPickerOpen(false);
  };

  const randomPick = () => {
    if (regionTree.length === 0) return;
    const p = regionTree[0];
    const city = p.children[Math.floor(Math.random() * p.children.length)];
    if (!city) return;
    const district = city.children[Math.floor(Math.random() * city.children.length)];
    if (!district) return;
    const street = district.children[Math.floor(Math.random() * district.children.length)];
    if (!street) return;
    setPickerSel({ province: p.name, city: city.name, district: district.name, street: street.name });
  };

  // ========== 组队挑战 ==========
  const loadChallenges = useCallback(async () => {
    try {
      const res = await api.get('/api/brain-game/challenges/mine');
      const data = res.data || res;
      setActiveChallenges(data.active || []);
      setHistoryChallenges(data.history || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (view === 'team') loadChallenges();
  }, [view, loadChallenges]);

  const createChallenge = async () => {
    try {
      const res = await api.post('/api/brain-game/challenges', { difficulty: teamDiff, team_size: teamSize });
      const data = res.data || res;
      alert(`挑战已创建！\n挑战编号：${data.code}\n\n请分享编号给好友，好友加入后即可开始答题PK！`);
      loadChallenges();
    } catch { alert('创建挑战失败'); }
  };

  const joinChallenge = () => {
    const code = prompt('请输入挑战编号：');
    if (!code) return;
    api.post('/api/brain-game/challenges/join', { code })
      .then((res: any) => {
        const data = res.data || res;
        alert(`已加入挑战：${data.challenge_code}\n\n请开始答题吧！`);
        loadChallenges();
        setCurrentChallengeId(data.challenge_id);
        setDifficulty(data.difficulty as Difficulty);
        startTeamGame(data.difficulty as Difficulty, data.challenge_id);
      })
      .catch((err: any) => {
        alert(err?.response?.data?.detail || '加入失败，请确认编号是否正确');
      });
  };

  // ========== 组队答题 ==========
  const startTeamGame = (diff: Difficulty, challengeId: number) => {
    setDifficulty(diff);
    setTeamCurrentQ(0);
    setTeamScore(0);
    setTeamRightCount(0);
    teamScoreRef.current = 0;
    teamRightRef.current = 0;
    setTeamTimeLeft(DIFF_CONFIG[diff].time);
    setTeamStartTime(Date.now());
    setTeamGameOver(false);
    setTeamAnswered(false);
    setCurrentChallengeId(challengeId);
    const qs: Question[] = [];
    for (let i = 0; i < 10; i++) qs.push(genQuestion(diff));
    setTeamQuestions(qs);
    navigate('team-game');
    startTeamTimer(DIFF_CONFIG[diff].time);
  };

  const startTeamTimer = (total: number) => {
    clearInterval(teamTimerRef.current!);
    teamTimerRef.current = setInterval(() => {
      setTeamTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(teamTimerRef.current!);
          finishTeamGame();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const teamAnswer = (val: number) => {
    if (teamAnswered) return;
    setTeamAnswered(true);
    const q = teamQuestions[teamCurrentQ];
    const correct = val === q.ans;
    if (correct) {
      const ns = teamScoreRef.current + 10;
      const nr = teamRightRef.current + 1;
      teamScoreRef.current = ns;
      teamRightRef.current = nr;
      setTeamScore(ns);
      setTeamRightCount(nr);
    }
    setTimeout(() => {
      if (teamCurrentQ >= 9) {
        finishTeamGame();
      } else {
        setTeamCurrentQ(c => c + 1);
        setTeamAnswered(false);
      }
    }, 600);
  };

  const finishTeamGame = () => {
    clearInterval(teamTimerRef.current!);
    setTeamGameOver(true);
    submitTeamScore();
  };

  const submitTeamScore = async () => {
    if (!currentChallengeId) return;
    const used = Math.min(
      Math.floor((Date.now() - teamStartTime) / 1000),
      DIFF_CONFIG[difficulty].time
    );
    try {
      await api.post(`/api/brain-game/challenges/${currentChallengeId}/submit-score`, {
        difficulty,
        score: teamScoreRef.current,
        right_count: teamRightRef.current,
        total_count: 10,
        time_seconds: used,
      });
    } catch { /* ignore */ }
    loadChallengeDetail(currentChallengeId);
  };

  const loadChallengeDetail = async (id: number) => {
    try {
      const res = await api.get(`/api/brain-game/challenges/${id}`);
      setChallengeDetail(res.data || res);
      navigate('team-result');
    } catch { /* ignore */ }
  };

  const openChallengeFromList = async (item: ChallengeItem) => {
    if (item.status === 'active') {
      // Check if current user has already answered
      await loadChallengeDetail(item.id);
      // Start game if not done
      setCurrentChallengeId(item.id);
      setDifficulty(item.difficulty as Difficulty);
      startTeamGame(item.difficulty as Difficulty, item.id);
    } else {
      await loadChallengeDetail(item.id);
    }
  };

  // ========== 分享 ==========
  const showShare = () => setShareOpen(true);
  const hideShare = () => setShareOpen(false);
  const doShare = (type: string) => {
    hideShare();
    alert(`已分享到${type}！好友点击链接即可加入。`);
  };

  // ========== 导航栏组件 ==========
  const NavBar = ({ title, onBack }: { title: string; onBack: () => void }) => (
    <div className="nav-bar">
      <div className="back-btn" onClick={onBack}>‹</div>
      <div className="nav-title">{title}</div>
    </div>
  );

  const nick = userInfo?.nickname || '用户';
  const avatarChar = nick[0] || '用';
  const locDisplay = myLoc.street
    ? `${myLoc.province}${myLoc.city}${myLoc.district}${myLoc.street}`
    : '';

  // 获取地区选择器的列表
  const getPickerItems = (level: keyof MyLoc): { name: string; adcode: string }[] => {
    if (regionTree.length === 0) return [];
    if (level === 'province') return regionTree.map(p => ({ name: p.name, adcode: p.adcode }));
    const p = regionTree.find(r => r.name === pickerSel.province);
    if (!p) return [];
    if (level === 'city') return p.children.map(c => ({ name: c.name, adcode: c.adcode }));
    const c = p.children.find(cc => cc.name === pickerSel.city);
    if (!c) return [];
    if (level === 'district') return c.children.map(d => ({ name: d.name, adcode: d.adcode }));
    const d = c.children.find(dd => dd.name === pickerSel.district);
    if (!d) return [];
    if (level === 'street') return d.children.map(s => ({ name: s.name, adcode: s.adcode }));
    return [];
  };

  return (
    <div className="brain-game-container">
      <div className="container">
        {/* ========== 首页 ========== */}
        <div className={`page ${view === 'home' ? 'active' : ''}`}>
          <div className="top-bar">
            <div className="user-info">
              <div className="avatar">{avatarChar}</div>
              <div>
                <div className="user-name">{nick}</div>
                <div className="user-loc">{locDisplay ? `📍 ${locDisplay}` : '📍 请先选择居住街道'}</div>
              </div>
            </div>
            <div className="change-loc" onClick={() => navigate('ranking')}>切换</div>
          </div>
          <div className="page-title">
            <h1>益智乐园</h1>
            <p>动动脑，更年轻</p>
          </div>
          <div className="menu-grid">
            <div className="menu-card card-math" onClick={() => navigate('math-difficulty')}>
              <div className="card-icon">🧮</div>
              <div className="card-title">数学游戏</div>
              <div className="card-subs">
                <span className="sub-item">基础</span><span className="dot">·</span>
                <span className="sub-item">进阶</span><span className="dot">·</span>
                <span className="sub-item">挑战</span>
              </div>
              <div className="card-desc">每天动动脑，越玩越聪明</div>
            </div>
            <div className="menu-card card-rank" onClick={() => navigate('ranking')}>
              <div className="card-icon">🏆</div>
              <div className="card-title">排行榜</div>
              <div className="card-subs">
                <span className="sub-item">街道</span><span className="dot">·</span>
                <span className="sub-item">区域</span><span className="dot">·</span>
                <span className="sub-item">城市</span>
              </div>
              <div className="card-desc">看看您在街坊邻居中排第几</div>
            </div>
            <div className="menu-card card-team" onClick={() => navigate('team')}>
              <div className="card-icon">👥</div>
              <div className="card-title">组队挑战</div>
              <div className="card-subs">
                <span className="sub-item">组队</span><span className="dot">·</span>
                <span className="sub-item">PK</span><span className="dot">·</span>
                <span className="sub-item">排行</span>
              </div>
              <div className="card-desc">邀请好友一起答题，比比谁的队伍更强</div>
            </div>
          </div>
          <div className="footer">益智乐园 · 让晚年更精彩</div>
        </div>

        {/* ========== 数学游戏 - 难度选择 ========== */}
        <div className={`page ${view === 'math-difficulty' ? 'active' : ''}`}>
          <NavBar title="数学游戏" onBack={() => navigate('home')} />
          <div className="difficulty-title">
            <h1>选择难度</h1>
            <p>循序渐进，越玩越聪明</p>
          </div>
          <div className="difficulty-grid">
            {(['basic', 'mid', 'hard'] as Difficulty[]).map(d => (
              <div key={d} className={`diff-card diff-${d}`} onClick={() => startGame(d)}>
                <div className="diff-icon">{DIFF_CONFIG[d].emoji}</div>
                <div className="diff-info">
                  <div className="diff-name">{DIFF_CONFIG[d].label}</div>
                  <div className="diff-rule">{DIFF_CONFIG[d].rule}</div>
                  <div className="diff-time">⏱ {DIFF_CONFIG[d].time / 60}分钟 · 10道题</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ========== 数学游戏 - 答题 ========== */}
        <div className={`page ${view === 'math-game' ? 'active' : ''}`}>
          <NavBar title={DIFF_CONFIG[difficulty].label} onBack={() => {
            if (confirm('确定退出本次答题吗？得分将不会保存。')) {
              clearInterval(timerRef.current!);
              navigate('math-difficulty');
            }
          }} />
          <div className="game-header">
            <div className="game-stat">
              <div className="stat-item">
                <div className="stat-label">进度</div>
                <div className="stat-value">{currentQ + 1}/10</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">得分</div>
                <div className="stat-value">{score}</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">剩余时间</div>
                <div className="stat-value stat-time">{formatTimer(timeLeft)}</div>
              </div>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${((currentQ + 1) / 10) * 100}%` }}></div>
            </div>
          </div>
          <div className="question-box">
            <div className="question-num">第 {currentQ + 1} 题</div>
            <div className="question-text">{questions[currentQ]?.text} = ?</div>
          </div>
          <div className="answer-grid">
            {questions[currentQ]?.options.map((opt, i) => (
              <button
                key={i}
                className={`answer-btn${answered ? (opt === questions[currentQ].ans ? ' correct' : ' wrong') : ''}`}
                onClick={() => answerQuestion(opt)}
                disabled={answered}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        {/* ========== 数学游戏 - 结果 ========== */}
        <div className={`page ${view === 'math-result' ? 'active' : ''}`}>
          <NavBar title="答题结果" onBack={() => navigate('math-difficulty')} />
          <div className="result-card">
            <div className="result-emoji">
              {(scoreResult?.score || rightCount * 10) >= 90 ? '🏆' :
               (scoreResult?.score || rightCount * 10) >= 70 ? '👍' :
               (scoreResult?.score || rightCount * 10) >= 50 ? '😊' : '💪'}
            </div>
            <div className="result-title">
              {(scoreResult?.score || rightCount * 10) >= 90 ? '太厉害啦！' :
               (scoreResult?.score || rightCount * 10) >= 70 ? '真棒！' :
               (scoreResult?.score || rightCount * 10) >= 50 ? '不错哦~' : '继续加油！'}
            </div>
            <div className="result-sub">您完成了{DIFF_CONFIG[difficulty].label}</div>
            <div className="score-big">{scoreResult?.score || rightCount * 10}</div>
            <div className="score-label">本次得分</div>
            <div className="result-detail">
              <div className="detail-item">
                <div className="detail-num">{scoreResult?.right_count || rightCount}</div>
                <div className="detail-label">答对题数</div>
              </div>
              <div className="detail-item">
                <div className="detail-num">{scoreResult ? formatTimer(scoreResult.time_seconds) : '—'}</div>
                <div className="detail-label">用时</div>
              </div>
              <div className="detail-item">
                <div className="detail-rank">
                  {scoreResult?.street_rank ? `第 ${scoreResult.street_rank} 名` : '第 — 名'}
                </div>
                <div className="detail-label">街道排名</div>
              </div>
            </div>
            <div className="btn-row">
              <button className="big-btn btn-share-btn" onClick={showShare}>📨 邀请好友来挑战</button>
              <button className="big-btn btn-primary" onClick={() => navigate('math-difficulty')}>再玩一次</button>
              <button className="big-btn btn-second" onClick={() => navigate('ranking')}>查看排行榜</button>
            </div>
          </div>
        </div>

        {/* ========== 排行榜 ========== */}
        <div className={`page ${view === 'ranking' ? 'active' : ''}`}>
          <NavBar title="排行榜" onBack={() => navigate('home')} />
          <div className="loc-card">
            <div className="loc-info">
              <div className="loc-label">我的居住地</div>
              <div className="loc-path">
                {locDisplay || <span className="empty">尚未选择，点击右侧设置</span>}
              </div>
            </div>
            <button className="loc-btn" onClick={openPicker}>选择街道</button>
          </div>
          <div className="myrank-grid">
            <div className="mr-card">
              <div className="mr-label">街道排名</div>
              <div className={`mr-num${myRanks.street === null ? ' empty' : ''}`}>
                {myRanks.street !== null ? myRanks.street : '—'}
              </div>
              <div className="mr-unit">/ {rankTotal} 人</div>
            </div>
            <div className="mr-card">
              <div className="mr-label">区域排名</div>
              <div className={`mr-num${myRanks.district === null ? ' empty' : ''}`}>
                {myRanks.district !== null ? myRanks.district : '—'}
              </div>
              <div className="mr-unit">/ {rankTotal} 人</div>
            </div>
            <div className="mr-card">
              <div className="mr-label">城市排名</div>
              <div className={`mr-num${myRanks.city === null ? ' empty' : ''}`}>
                {myRanks.city !== null ? myRanks.city : '—'}
              </div>
              <div className="mr-unit">/ {rankTotal} 人</div>
            </div>
          </div>
          <div className="tabs">
            {(['street', 'district', 'city'] as RankTab[]).map(t => (
              <div
                key={t}
                className={`tab${rankTab === t ? ' active' : ''}`}
                onClick={() => setRankTab(t)}
              >
                {t === 'street' ? '街道榜' : t === 'district' ? '区榜' : '市榜'}
              </div>
            ))}
          </div>
          <div className="rank-list">
            {rankList.length === 0 ? (
              <div className="empty-tip">
                <div className="emoji">📍</div>
                <p>{myLoc.street ? '暂无排行数据' : '请先选择您所在的街道\n才能看到对应排行榜'}</p>
              </div>
            ) : (
              rankList.map(r => {
                const noClass = r.rank === 1 ? 'top1' : r.rank === 2 ? 'top2' : r.rank === 3 ? 'top3' : '';
                const noText = r.rank === 1 ? '🥇' : r.rank === 2 ? '🥈' : r.rank === 3 ? '🥉' : r.rank;
                return (
                  <div key={r.user_id} className={`rank-row${r.is_me ? ' me' : ''}`}>
                    <div className={`rk-no ${noClass}`}>{noText}</div>
                    <div className="rk-avatar">{(r.nickname || '用')[0]}</div>
                    <div className="rk-name">
                      {r.nickname}
                      {r.is_me && <span className="me-tag">我</span>}
                    </div>
                    <div className="rk-score">{r.score}分</div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ========== 组队挑战 ========== */}
        <div className={`page ${view === 'team' ? 'active' : ''}`}>
          <NavBar title="组队挑战" onBack={() => navigate('home')} />
          <div className="team-card">
            <h3>🚩 发起组队挑战</h3>
            <div className="team-form-row">
              <label>难度</label>
              <select className="team-select" value={teamDiff} onChange={e => setTeamDiff(e.target.value as Difficulty)}>
                <option value="basic">基础训练（3分钟）</option>
                <option value="mid">进阶训练（5分钟）</option>
                <option value="hard">挑战训练（10分钟）</option>
              </select>
            </div>
            <div className="team-form-row">
              <label>队伍人数</label>
              <select className="team-select" value={teamSize} onChange={e => setTeamSize(Number(e.target.value))}>
                <option value="2">2 人</option>
                <option value="3">3 人</option>
                <option value="4">4 人</option>
                <option value="5">5 人</option>
              </select>
            </div>
            <button className="big-btn btn-primary" style={{ width: '100%' }} onClick={createChallenge}>发起挑战</button>
            <button className="big-btn btn-second" style={{ width: '100%', marginTop: 10 }} onClick={joinChallenge}>🔗 加入已有挑战</button>
          </div>
          <div className="section-title">📋 进行中的挑战</div>
          <div className="challenge-list">
            {activeChallenges.length === 0 ? (
              <div className="empty-tip"><div className="emoji">📭</div><p>暂无进行中的挑战<br />快发起一个吧！</p></div>
            ) : (
              activeChallenges.map(c => (
                <div key={c.id} className="challenge-item" onClick={() => openChallengeFromList(c)}>
                  <div className="challenge-info">
                    <span className="challenge-code">{c.code}</span>
                    <div className="challenge-desc">{c.difficulty_name} · {c.team_size}人队</div>
                    <div className="challenge-meta">已完成 {c.done_count}/{c.member_count} 人</div>
                  </div>
                  <div className="challenge-status active-c">进行中</div>
                </div>
              ))
            )}
          </div>
          <div className="section-title">📜 挑战历史</div>
          <div className="challenge-list">
            {historyChallenges.length === 0 ? (
              <div className="empty-tip"><div className="emoji">📜</div><p>暂无历史记录</p></div>
            ) : (
              historyChallenges.slice(0, 10).map(c => (
                <div key={c.id} className="challenge-item" onClick={() => loadChallengeDetail(c.id)}>
                  <div className="challenge-info">
                    <span className="challenge-code">{c.code}</span>
                    <div className="challenge-desc">{c.difficulty_name} · {c.team_size}人队</div>
                    <div className="challenge-meta">队伍总分：{c.total_score || '—'} 分</div>
                  </div>
                  <div className="challenge-status done">已结束</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ========== 组队答题 ========== */}
        <div className={`page ${view === 'team-game' ? 'active' : ''}`}>
          <NavBar title={`组队答题 - ${DIFF_CONFIG[difficulty].label}`} onBack={() => {
            if (confirm('确定退出组队答题吗？得分将不会保存。')) {
              clearInterval(teamTimerRef.current!);
              navigate('team');
            }
          }} />
          <div className="game-header">
            <div className="game-stat">
              <div className="stat-item">
                <div className="stat-label">进度</div>
                <div className="stat-value">{teamCurrentQ + 1}/10</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">得分</div>
                <div className="stat-value">{teamScore}</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">剩余时间</div>
                <div className="stat-value stat-time">{formatTimer(teamTimeLeft)}</div>
              </div>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${((teamCurrentQ + 1) / 10) * 100}%` }}></div>
            </div>
          </div>
          <div className="question-box">
            <div className="question-num">第 {teamCurrentQ + 1} 题</div>
            <div className="question-text">{teamQuestions[teamCurrentQ]?.text} = ?</div>
          </div>
          <div className="answer-grid">
            {teamQuestions[teamCurrentQ]?.options.map((opt, i) => (
              <button
                key={i}
                className={`answer-btn${teamAnswered ? (opt === teamQuestions[teamCurrentQ]?.ans ? ' correct' : ' wrong') : ''}`}
                onClick={() => teamAnswer(opt)}
                disabled={teamAnswered}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        {/* ========== 组队结果 ========== */}
        <div className={`page ${view === 'team-result' ? 'active' : ''}`}>
          <NavBar title="挑战结果" onBack={() => navigate('team')} />
          {challengeDetail && (
            <div className="team-result-card">
              <h3 style={{ fontSize: 22, color: '#0d47a1', marginBottom: 16 }}>🏆 {challengeDetail.code} 挑战结果</h3>
              <div style={{ fontSize: 16, color: '#5c7ea3', marginBottom: 16 }}>
                {DIFF_CONFIG[challengeDetail.difficulty as Difficulty]?.label || challengeDetail.difficulty} · {challengeDetail.team_size}人队
              </div>
              <div style={{ fontSize: 36, fontWeight: 'bold', color: '#0288d1', marginBottom: 20 }}>
                队伍总分：{challengeDetail.total_score || '—'} 分
              </div>
              {challengeDetail.members.map((m, i) => {
                const medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '';
                const isMe = m.user_id === userInfo?.user_id;
                return (
                  <div key={m.user_id} className={`rank-row${isMe ? ' me' : ''}`}>
                    <div style={{ width: 30, fontSize: 20 }}>{medal}</div>
                    <div className="rk-avatar">{m.nickname[0]}</div>
                    <div className="rk-name">
                      {m.nickname}
                      {isMe && <span className="me-tag">我</span>}
                      {!m.done && <span style={{ fontSize: 12, color: '#ff9800', marginLeft: 6 }}>等待中...</span>}
                    </div>
                    <div className="rk-score">{m.done ? `${m.score}分` : '—'}</div>
                  </div>
                );
              })}
              {challengeDetail.status === 'active' && (
                <div style={{ fontSize: 14, color: '#ff9800', marginTop: 8 }}>⏳ 等待其他队员完成答题...</div>
              )}
            </div>
          )}
          <div className="btn-row">
            <button className="big-btn btn-share-btn" onClick={showShare}>📨 分享成绩</button>
            <button className="big-btn btn-primary" onClick={() => navigate('team')}>返回挑战</button>
          </div>
        </div>
      </div>

      {/* ========== 四级联动选择器弹窗 ========== */}
      {pickerOpen && (
        <div className="picker-mask show" onClick={(e) => { if (e.target === e.currentTarget) closePicker(); }}>
          <div className="picker-panel">
            <div className="picker-head">
              <span className="picker-cancel" onClick={closePicker}>取消</span>
              <h3>选择我的街道</h3>
              <span className="picker-confirm" onClick={confirmPicker}>完成</span>
            </div>
            <div className="picker-path">
              {pickerSel.province ? (
                <>
                  <span className="pp-item">{pickerSel.province}</span>
                  {pickerSel.city && <><span className="pp-arrow">›</span><span className="pp-item">{pickerSel.city}</span></>}
                  {pickerSel.district && <><span className="pp-arrow">›</span><span className="pp-item">{pickerSel.district}</span></>}
                  {pickerSel.street && <><span className="pp-arrow">›</span><span className="pp-item">{pickerSel.street}</span></>}
                </>
              ) : (
                <span className="pp-empty">请依次选择：省 → 市 → 区 → 街道</span>
              )}
            </div>
            <div className="picker-cols">
              {(['province', 'city', 'district', 'street'] as (keyof MyLoc)[]).map((level, idx) => (
                <div key={level} className="picker-col">
                  <div className="picker-col-head">
                    {idx === 0 ? '省份' : idx === 1 ? '城市' : idx === 2 ? '区/县' : '街道'}
                  </div>
                  {getPickerItems(level).length === 0 ? (
                    <div className="col-empty">
                      {idx === 0 ? '暂无数据' : `请先选${idx === 1 ? '省' : idx === 2 ? '市' : '区'}`}
                    </div>
                  ) : (
                    getPickerItems(level).map(item => (
                      <div
                        key={item.adcode}
                        className={`picker-item${pickerSel[level] === item.name ? ' selected' : ''}`}
                        onClick={() => selectPickerItem(level, item.name)}
                      >
                        {item.name}
                      </div>
                    ))
                  )}
                </div>
              ))}
            </div>
            <div className="picker-foot">
              <button className="pf-btn pf-skip" onClick={randomPick}>随便选一个</button>
              <button
                className="pf-btn pf-ok"
                onClick={confirmPicker}
                disabled={!pickerSel.province || !pickerSel.city || !pickerSel.district || !pickerSel.street}
              >
                确定
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== 浮动分享按钮 ========== */}
      <div className="float-share" onClick={showShare} title="邀请好友">📨</div>

      {/* ========== 分享弹窗 ========== */}
      {shareOpen && (
        <div className="modal-mask show" onClick={(e) => { if (e.target === e.currentTarget) hideShare(); }}>
          <div className="modal">
            <h3>邀请好友一起玩</h3>
            <div className="share-options">
              <div className="share-opt" onClick={() => doShare('微信好友')}>
                <div className="si">💬</div>
                <div className="sl">微信好友</div>
              </div>
              <div className="share-opt" onClick={() => doShare('朋友圈')}>
                <div className="si">👥</div>
                <div className="sl">朋友圈</div>
              </div>
              <div className="share-opt" onClick={() => doShare('海报')}>
                <div className="si">🖼</div>
                <div className="sl">生成海报</div>
              </div>
            </div>
            <div className="modal-close" onClick={hideShare}>取消</div>
          </div>
        </div>
      )}
    </div>
  );
}
