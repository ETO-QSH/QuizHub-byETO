let qlist = []; let pos = 0; let mode = null;
let currentQuestion = null;
let multiSelected = new Set();
let revealMode = false;
let ud_cache = null; // 缓存用户数据
let progressKey = null; // 后端返回的进度键
let explainMode = false; // 是否显示解析

let isTagMode = false;
let tempQA = {};
let ignoreHistoryOnEntry = false;
let firstLoad = true;

async function loadProgressList(){
  ud_cache = await fetch('/api/user/data').then(r=>r.json());
  const flags = await fetch('/api/flags').then(r=>r.json());
  explainMode = !!flags.show_explanations;
  
  progressKey = ud_cache.current_progress_key || null;
  const progObj = ud_cache.progress || {};
  if(!progressKey){
    const keys = Object.keys(progObj || {});
    if(keys.length>0){
      progressKey = keys[0];
    }
  }

  isTagMode = Boolean(progressKey && (progressKey === 'wrong' || progressKey === 'star' || (typeof progressKey === 'string' && progressKey.startsWith('random:'))));

  if(progressKey && progObj[progressKey]){
    const prog = progObj[progressKey];
    qlist = prog.list || [];
    pos = prog.pos || 0;
    revealMode = !!prog.reveal;
  } else {
    qlist = [];
    pos = 0;
    revealMode = false;
  }

  // 特殊模式（tag/random/star）：在进入 quiz 的“首次加载”阶段临时忽略历史作答显示/禁答判定，
  // 但不要破坏 ud_cache（只读不写），并且题目的标星状态仍从 ud_cache.global 读取用于展示。
  if(isTagMode){
    ignoreHistoryOnEntry = true;
    firstLoad = true;
    tempQA = {};
  } else {
    ignoreHistoryOnEntry = false;
    firstLoad = true;
  }

  renderList();
  loadQuestion();
}

function renderList(){
  const container = document.getElementById('list'); container.innerHTML = '';
  qlist.forEach((uid,i)=>{
    const el = document.createElement('div');
    el.id = 'li-'+i;
    el.className = 'uid-square';
    el.innerText = uid;
    el.title = uid;
    el.onclick = ()=>{ pos = i; savePos(); loadQuestion(); };

    // 标星状态始终读取并展示（进入时就要显示题目的标星状态）
    if(ud_cache && ud_cache.global && Array.isArray(ud_cache.global.star) && ud_cache.global.star.includes(uid)){
      el.dataset.star = "1";
    }

    // 历史答题标记逻辑：
    // - 特殊模式（isTagMode）：使用 tempQA 判断本模式内是否已做（做过则标颜色），不使用全局 last_choice
    // - 非特殊模式：正常使用 ud_cache.last_choice 显示历史
    if(isTagMode){
      const t = tempQA && tempQA[uid];
      if(t){
        if(t.correct) el.classList.add('green'); else el.classList.add('red');
      }
    } else {
      if(!(ignoreHistoryOnEntry && firstLoad) && ud_cache){
        const last = ud_cache.last_choice && ud_cache.last_choice[uid];
        const gl = ud_cache.global || {wrong:[], star:[]};
        if(last && last.correct) el.classList.add('green');
        else if(last && !last.correct) el.classList.add('red');
        if(gl.star && gl.star.includes(uid)) el.dataset.star = "1";
      }
    }

    if(i===pos) el.classList.add('active');
    container.appendChild(el);
  });
  adjustGridSize();
}

function adjustGridSize(){
  const grid = document.getElementById('list');
  if(!grid) return;
  const rootStyle = getComputedStyle(document.documentElement);
  const cols = parseInt(rootStyle.getPropertyValue('--grid-columns')) || 5;
  const gap = parseFloat(rootStyle.getPropertyValue('--grid-gap')) || 8;
  const rowsVisible = parseInt(rootStyle.getPropertyValue('--grid-rows-visible')) || 10;

  const col = grid.closest('.col-lg-4') || grid.closest('.col-md-4') || grid.parentElement;
  const colWidth = col ? col.clientWidth : 0;
  const parentWidth = grid.parentElement ? grid.parentElement.clientWidth : 0;
  let availableWidth = Math.max(colWidth, parentWidth);
  if (!availableWidth) availableWidth = 600;

  const gridCS = getComputedStyle(grid);
  const gridPadLeft = parseFloat(gridCS.paddingLeft) || 0;
  const gridPadRight = parseFloat(gridCS.paddingRight) || 0;
  const gridPaddingTotal = gridPadLeft + gridPadRight;

  const card = grid.closest('.card');
  let cardInnerPad = 24;
  if (card){
    const cb = card.querySelector('.card-body');
    if(cb){
      const cbCS = getComputedStyle(cb);
      const cbPadLeft = parseFloat(cbCS.paddingLeft) || 0;
      const cbPadRight = parseFloat(cbCS.paddingRight) || 0;
      cardInnerPad = cbPadLeft + cbPadRight;
    }
  }
  const extraMargin = 24;
  const paddingExtra = cardInnerPad + extraMargin;

  const cssMax = parseInt(rootStyle.getPropertyValue('--square-size')) || 56;
  let single = Math.floor((availableWidth - paddingExtra - gridPaddingTotal - gap * (cols - 1)) / cols);
  if(single > cssMax) single = cssMax;
  if(single < 16) single = 16;

  let gridWidth = single * cols + gap * (cols - 1);
  let totalNeeded = gridWidth + paddingExtra + gridPaddingTotal;
  if(totalNeeded > availableWidth){
    single = Math.floor((availableWidth - paddingExtra - gridPaddingTotal - gap * (cols - 1)) / cols);
    if(single < 16) single = 16;
    gridWidth = single * cols + gap * (cols - 1);
    totalNeeded = gridWidth + paddingExtra + gridPaddingTotal;
  }

  if(single > cssMax) single = cssMax;
  if(single < 16) single = 16;

  // 固定每列像素宽，保证方块大小不随容器变化
  grid.style.gridTemplateColumns = `repeat(${cols}, ${single}px)`;
  grid.style.gridAutoRows = single + 'px';

  // 留白不改变方块尺寸，但扩大容器视觉宽度（不超出 availableWidth）
  const extraPad = Math.floor(single * 1.0);
  let targetGridWidth = gridWidth + extraPad * 2;
  const maxGridArea = Math.max(availableWidth - paddingExtra - gridPaddingTotal, gridWidth);
  if(targetGridWidth > maxGridArea) targetGridWidth = Math.max(gridWidth, maxGridArea);
  grid.style.width = Math.floor(targetGridWidth) + 'px';

  grid.style.overflowX = 'hidden';
  // 不在 grid 上设置 maxHeight；改为让外层 card（card-body）承载垂直滚动
  if(card){
    // 计算期望用于显示 rowsVisible 行的网格高度（仅网格部分）
    const desiredGridHeight = Math.floor(single * rowsVisible + gap * (rowsVisible - 1));
    // 将卡片最大高度设置为网格高度 + 内边距补偿（确保滚动条在卡片上）
    const desiredCardMax = desiredGridHeight + paddingExtra + gridPaddingTotal;
    let desiredCardWidth = Math.floor(parseFloat(grid.style.width) + paddingExtra + gridPaddingTotal);
    // 缩小卡片宽度 24px
    desiredCardWidth = Math.max(desiredCardWidth - 24, 0);
    if(col && desiredCardWidth > col.clientWidth){
      desiredCardWidth = col.clientWidth;
    }
    card.style.width = desiredCardWidth + 'px';
    card.style.maxWidth = desiredCardWidth + 'px';
    card.style.marginLeft = 'auto';
    card.style.marginRight = '0';
    // 将高度与滚动交给 card-body（card 本身可能包含标题等）
    const cb = card.querySelector('.card-body');
    if(cb){
      cb.style.maxHeight = desiredCardMax + 'px';
      cb.style.overflowY = 'auto';
    }
  }
}

async function loadQuestion(){
  multiSelected.clear();
  // 切换题目时不全局清空 tempQA，这样同一次进入模式里可保留临时答题结果

  const submitBtn = document.getElementById('submitBtn');
  if(submitBtn) submitBtn.style.display = 'none';

  if(pos>=qlist.length){ document.getElementById('qtitle').innerText='已完成'; return; }
  highlightList();

  const uid = qlist[pos];
  let q = await fetch('/api/question?uid='+encodeURIComponent(uid) + (revealMode ? '&reveal=1' : '')).then(r=>r.json());
  currentQuestion = q;
  document.getElementById('qtitle').innerText = (pos+1)+'. '+ q.question;
  const opts = document.getElementById('opts'); opts.innerHTML = '';
  document.getElementById('feedback').innerText = '';

  const explainBox = document.getElementById('explanation-box');
  if(explainBox) explainBox.remove();

  // 读取历史作答来源：
  // - 若处于特殊模式（isTagMode），只看 tempQA（本模式内做过则视为已作答）；外部做过（ud_cache.last_choice）不影响
  // - 否则按之前逻辑（首次进入且忽略历史时视为无历史）
  const rawLast = (ud_cache && ud_cache.last_choice) ? ud_cache.last_choice[uid] : null;
  let last = null;
  if(isTagMode){
    last = (tempQA && tempQA[uid]) ? tempQA[uid] : null;
  } else {
    last = (ignoreHistoryOnEntry && firstLoad) ? null : rawLast;
  }

  const gl = ud_cache && ud_cache.global ? ud_cache.global : {wrong:[], star:[]};
  setStarVisual(gl.star && gl.star.includes(uid));

  if((revealMode || last) && (q.answer === undefined || q.answer === null)){
    try{
      const qWithAnswer = await fetch('/api/question?uid='+encodeURIComponent(uid)+'&reveal=1').then(r=>r.json());
      if(qWithAnswer && (qWithAnswer.answer !== undefined)) {
        q.answer = qWithAnswer.answer;
        currentQuestion.answer = qWithAnswer.answer;
      }
    }catch(e){
      console.warn('无法获取题目正确答案用于渲染', e);
    }
  }

  // 只要处于背题模式就禁用；否则若 last（来源按上面计算）存在也禁用
  const shouldDisable = revealMode || !!last;

  if(q.type === '判断题'){
    for(const k of Object.keys(q.options)){
      const b = document.createElement('button');
      b.className = 'option-btn';
      b.innerText = k + ' ' + q.options[k];
      if(!shouldDisable) b.onclick = ()=>submitAnswerSingle(uid, k);
      else { b.onclick = null; b.style.pointerEvents = 'none'; }
      opts.appendChild(b);
    }
    if(submitBtn) submitBtn.style.display = 'none';
  } else if(q.type === '多选题'){
    for(let k in q.options){
      const b = document.createElement('button');
      b.className = 'option-btn';
      b.id = 'opt-'+k;
      b.innerText = k + '. ' + q.options[k];
      if(!shouldDisable) b.onclick = ()=>{ toggleMultiOption(k); };
      else { b.onclick = null; b.style.pointerEvents = 'none'; }
      opts.appendChild(b);
    }
    if(submitBtn && !shouldDisable){ submitBtn.style.display = 'inline-block'; submitBtn.onclick = ()=>submitAnswerMulti(uid); }
    else if(submitBtn) submitBtn.style.display = 'none';
  } else {
    for(let k in q.options){
      const b = document.createElement('button');
      b.className = 'option-btn';
      b.innerText = k + '. ' + q.options[k];
      if(!shouldDisable) b.onclick = ()=>submitAnswerSingle(uid, k);
      else { b.onclick = null; b.style.pointerEvents = 'none'; }
      opts.appendChild(b);
    }
    if(submitBtn) submitBtn.style.display = 'none';
  }

  // 显示答案与解析
  if(q.answer !== undefined && q.answer !== null){
    const optsArr = document.querySelectorAll('#opts .option-btn');
    optsArr.forEach(btn=>{
      const txt = btn.innerText.trim();
      const key = txt.split(/[.\s]/)[0];
      btn.classList.remove('correct','wrong','selected');
      
      if(revealMode){
        if(Array.isArray(q.answer)){
          if(q.answer.includes(key)) btn.classList.add('correct');
          else btn.classList.add('wrong');
        } else {
          if(q.answer === key) btn.classList.add('correct');
          else btn.classList.add('wrong');
        }
      } else if(last && !isTagMode){
        if(Array.isArray(last.selected) && last.selected.includes(key)) btn.classList.add('selected');
        if(Array.isArray(q.answer)){
          if(q.answer.includes(key)) btn.classList.add('correct');
          if(Array.isArray(last.selected) && last.selected.includes(key) && !q.answer.includes(key)) btn.classList.add('wrong');
        } else {
          if(q.answer === key) btn.classList.add('correct');
          if(last.selected === key && last.selected !== q.answer) btn.classList.add('wrong');
        }
        if(q.type === '多选题' && Array.isArray(last.selected)){
          multiSelected.clear();
          last.selected.forEach(k=>multiSelected.add(k));
        }
      }
    });

    // tag 模式：不更新方块颜色
    if(!isTagMode){
      const square = document.getElementById('li-'+pos);
      if(square && (revealMode || last)){
        square.classList.remove('green','red');
        if(last){
          if(last.correct) square.classList.add('green'); else square.classList.add('red');
        }
      }
    }

    // tag 模式：不显示反馈；其他模式正常显示
    if(!isTagMode){
      if(revealMode){
        // 背题模式：不显示反馈
      } else if(last){
        document.getElementById('feedback').innerText = last.correct ? '✓ 回答正确' : ('✗ 回答错误，正确答案: ' + (Array.isArray(q.answer) ? JSON.stringify(q.answer) : q.answer));
      }
    }

    if((revealMode || (explainMode && last && !isTagMode)) && q.explanation){
      const feedbackDiv = document.getElementById('feedback');
      const explainDiv = document.createElement('div');
      
      explainDiv.id = explainDiv.id || 'explanation-box';
      explainDiv.style.display = 'block';
      explainDiv.style.width = '100%';
      explainDiv.style.boxSizing = 'border-box';
      
      const leftCol = feedbackDiv && feedbackDiv.parentElement;
      const controlRow = leftCol && leftCol.parentElement;
      if (controlRow && controlRow.parentElement) {
        controlRow.parentElement.insertBefore(explainDiv, controlRow.nextSibling);
      } else if (feedbackDiv && feedbackDiv.parentElement) {
        feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
      }
      explainDiv.style.marginTop = '12px';
      explainDiv.style.padding = '10px';
      explainDiv.style.backgroundColor = '#f0f8ff';
      explainDiv.style.borderLeft = '4px solid #0d6efd';
      explainDiv.style.fontSize = '13px';
      explainDiv.style.lineHeight = '1.5';
      explainDiv.innerText = '💡 ' + q.explanation;
    }
  }

  // 在首次加载完成后，取消“首次忽略历史”状态，使后续题目恢复正常读取历史
  if(ignoreHistoryOnEntry && firstLoad){
    firstLoad = false;
    // 我们只在进入时忽略一次，随后恢复正常读取历史
    ignoreHistoryOnEntry = false;
  }

  document.getElementById('starBtn').onclick = ()=>toggleStar(uid);
  document.getElementById('nextBtn').onclick = ()=>{ pos = Math.min(pos+1, qlist.length-1); savePos(); loadQuestion(); };
  document.getElementById('prevBtn').onclick = ()=>{ pos = Math.max(pos-1, 0); savePos(); loadQuestion(); };
}

function toggleMultiOption(key){
  if(multiSelected.has(key)) multiSelected.delete(key);
  else multiSelected.add(key);
  const btn = document.getElementById('opt-'+key);
  if(btn){
    if(multiSelected.has(key)) btn.classList.add('selected');
    else btn.classList.remove('selected');
  }
}

async function submitAnswerSingle(uid, selected){
  if(!currentQuestion) return;
  // 非特殊模式：若全局已有历史作答，禁止再次作答（防止绕过前端）
  if(!isTagMode && ud_cache && ud_cache.last_choice && ud_cache.last_choice[uid]){
    alert('该题已有历史作答记录，不能再次作答。');
    return;
  }
  // 特殊模式：若本模式已在 tempQA 中存在记录，也禁止再次作答
  if(isTagMode && tempQA && tempQA[uid]){
    alert('该题在本模式中已作答，不能重复作答。');
    return;
  }

  const r = await fetch('/api/answer',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({uid, selected})}).then(r=>r.json());
  const opts = document.querySelectorAll('#opts .option-btn');
  opts.forEach(btn=>{
    const txt = btn.innerText.trim();
    const key = txt.split(/[.\s]/)[0];
    btn.classList.remove('correct','wrong','selected');
    if(Array.isArray(r.answer)){
      if(r.answer.includes(key)) btn.classList.add('correct');
      if(key===selected && !r.answer.includes(key)) btn.classList.add('wrong');
    } else {
      if(key===r.answer) btn.classList.add('correct');
      if(key===selected && key!==r.answer) btn.classList.add('wrong');
    }
  });

  // tag/random 模式：不要写入后端持久记录，仅记录到 tempQA，防止本模式内重复作答
  if(isTagMode){
    tempQA[uid] = {"correct": r.correct, "selected": selected};
    // 显示解析（如启用）
    if(explainMode && currentQuestion.explanation){
      const feedbackDiv = document.getElementById('feedback');
      const explainDiv = document.createElement('div');
      
      explainDiv.id = explainDiv.id || 'explanation-box';
      explainDiv.style.display = 'block';
      explainDiv.style.width = '100%';
      explainDiv.style.boxSizing = 'border-box';
      
      const leftCol = feedbackDiv && feedbackDiv.parentElement;
      const controlRow = leftCol && leftCol.parentElement;
      if (controlRow && controlRow.parentElement) {
        controlRow.parentElement.insertBefore(explainDiv, controlRow.nextSibling);
      } else if (feedbackDiv && feedbackDiv.parentElement) {
        feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
      }
      explainDiv.style.marginTop = '12px';
      explainDiv.style.padding = '10px';
      explainDiv.style.backgroundColor = '#f0f8ff';
      explainDiv.style.borderLeft = '4px solid #0d6efd';
      explainDiv.style.fontSize = '13px';
      explainDiv.style.lineHeight = '1.5';
      explainDiv.innerText = '💡 ' + currentQuestion.explanation;
    }
    const optsArr = document.querySelectorAll('#opts .option-btn');
    optsArr.forEach(btn=>{ btn.onclick = null; btn.style.pointerEvents = 'none'; });
    // 在列表上标记该题已做（颜色）
    const square = document.getElementById('li-'+pos);
    if(square){ square.classList.remove('green','red'); if(r.correct) square.classList.add('green'); else square.classList.add('red'); }
    return;
  }

  // 非 tag 模式：正常保存数据
  ud_cache = ud_cache || {};
  ud_cache.last_choice = ud_cache.last_choice || {};
  ud_cache.last_choice[uid] = {"correct": r.correct, "selected": selected};
  ud_cache.global = ud_cache.global || {"wrong": [], "star": []};
  if(!r.correct){
    if(!ud_cache.global.wrong.includes(uid)) ud_cache.global.wrong.push(uid);
  } else {
    const idx = ud_cache.global.wrong.indexOf(uid); if(idx>=0) ud_cache.global.wrong.splice(idx,1);
  }
  const square = document.getElementById('li-'+pos);
  if(square){ square.classList.remove('green','red'); if(r.correct) square.classList.add('green'); else square.classList.add('red'); }
  document.getElementById('feedback').innerText = r.correct ? '✓ 回答正确' : ('✗ 回答错误，正确答案: ' + JSON.stringify(r.answer));
  
  const optsArr = document.querySelectorAll('#opts .option-btn');
  optsArr.forEach(btn=>{ btn.onclick = null; btn.style.pointerEvents = 'none'; });
  
  if(explainMode && currentQuestion.explanation){
    const feedbackDiv = document.getElementById('feedback');
    const explainDiv = document.createElement('div');
    
    explainDiv.id = explainDiv.id || 'explanation-box';
    explainDiv.style.display = 'block';
    explainDiv.style.width = '100%';
    explainDiv.style.boxSizing = 'border-box';
    
    const leftCol = feedbackDiv && feedbackDiv.parentElement;
    const controlRow = leftCol && leftCol.parentElement;
    if (controlRow && controlRow.parentElement) {
      controlRow.parentElement.insertBefore(explainDiv, controlRow.nextSibling);
    } else if (feedbackDiv && feedbackDiv.parentElement) {
      feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
    }
    explainDiv.style.marginTop = '12px';
    explainDiv.style.padding = '10px';
    explainDiv.style.backgroundColor = '#f0f8ff';
    explainDiv.style.borderLeft = '4px solid #0d6efd';
    explainDiv.style.fontSize = '13px';
    explainDiv.style.lineHeight = '1.5';
    explainDiv.innerText = '💡 ' + currentQuestion.explanation;
  }
  
  await saveProgress();
}

async function submitAnswerMulti(uid){
  if(!currentQuestion) return;
  // 安全保护：若非特殊模式且已有历史作答，禁止再次提交
  if(!isTagMode && ud_cache && ud_cache.last_choice && ud_cache.last_choice[uid]){
    alert('该题已有历史作答记录，不能再次作答。');
    return;
  }
  // 特殊模式：若本模式已在 tempQA 中存在记录，也禁止再次作答
  if(isTagMode && tempQA && tempQA[uid]){
    alert('该题在本模式中已作答，不能重复作答。');
    return;
  }

  const selectedArr = Array.from(multiSelected);
  const r = await fetch('/api/answer',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({uid, selected: selectedArr})}).then(r=>r.json());
  const correct = Array.isArray(r.answer) ? r.answer : (r.answer ? [r.answer] : []);
  const opts = document.querySelectorAll('#opts .option-btn');
  opts.forEach(btn=>{
    const txt = btn.innerText.trim();
    const key = txt.split(/[.\s]/)[0];
    btn.classList.remove('correct','wrong','selected');
    if(selectedArr.includes(key)) btn.classList.add('selected');
    if(correct.includes(key)) btn.classList.add('correct');
    if(selectedArr.includes(key) && !correct.includes(key)) btn.classList.add('wrong');
  });

  if(isTagMode){
    tempQA[uid] = {"correct": r.correct, "selected": selectedArr};
    if(explainMode && currentQuestion.explanation){
      const feedbackDiv = document.getElementById('feedback');
      const explainDiv = document.createElement('div');
      
      explainDiv.id = explainDiv.id || 'explanation-box';
      explainDiv.style.display = 'block';
      explainDiv.style.width = '100%';
      explainDiv.style.boxSizing = 'border-box';

      const leftCol = feedbackDiv && feedbackDiv.parentElement;
      const controlRow = leftCol && leftCol.parentElement;
      if (controlRow && controlRow.parentElement) {
        controlRow.parentElement.insertBefore(explainDiv, controlRow.nextSibling);
      } else if (feedbackDiv && feedbackDiv.parentElement) {
        feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
      }
      explainDiv.style.marginTop = '12px';
      explainDiv.style.padding = '10px';
      explainDiv.style.backgroundColor = '#f0f8ff';
      explainDiv.style.borderLeft = '4px solid #0d6efd';
      explainDiv.style.fontSize = '13px';
      explainDiv.style.lineHeight = '1.5';
      explainDiv.innerText = '💡 ' + currentQuestion.explanation;
    }
    const optsArr = document.querySelectorAll('#opts .option-btn');
    optsArr.forEach(btn=>{ btn.onclick = null; btn.style.pointerEvents = 'none'; });
    const square = document.getElementById('li-'+pos);
    if(square){ square.classList.remove('green','red'); if(r.correct) square.classList.add('green'); else square.classList.add('red'); }
    return;
  }

  // 非 tag 模式：正常保存数据
  ud_cache = ud_cache || {};
  ud_cache.last_choice = ud_cache.last_choice || {};
  ud_cache.last_choice[uid] = {"correct": r.correct, "selected": selectedArr};
  ud_cache.global = ud_cache.global || {"wrong": [], "star": []};
  if(!r.correct){
    if(!ud_cache.global.wrong.includes(uid)) ud_cache.global.wrong.push(uid);
  } else {
    const idx = ud_cache.global.wrong.indexOf(uid); if(idx>=0) ud_cache.global.wrong.splice(idx,1);
  }
  const square = document.getElementById('li-'+pos);
  if(square){ square.classList.remove('green','red'); if(r.correct) square.classList.add('green'); else square.classList.add('red'); }
  document.getElementById('feedback').innerText = r.correct ? '✓ 回答正确' : ('✗ 回答错误，正确答案: ' + JSON.stringify(r.answer));
  
  const optsArr = document.querySelectorAll('#opts .option-btn');
  optsArr.forEach(btn=>{ btn.onclick = null; btn.style.pointerEvents = 'none'; });
  
  if(explainMode && currentQuestion.explanation){
    const feedbackDiv = document.getElementById('feedback');
    const explainDiv = document.createElement('div');
    
    explainDiv.id = explainDiv.id || 'explanation-box';
    explainDiv.style.display = 'block';
    explainDiv.style.width = '100%';
    explainDiv.style.boxSizing = 'border-box';
    
    const leftCol = feedbackDiv && feedbackDiv.parentElement;
    const controlRow = leftCol && leftCol.parentElement;
    if (controlRow && controlRow.parentElement) {
      controlRow.parentElement.insertBefore(explainDiv, controlRow.nextSibling);
    } else if (feedbackDiv && feedbackDiv.parentElement) {
      feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
    }
    explainDiv.style.marginTop = '12px';
    explainDiv.style.padding = '10px';
    explainDiv.style.backgroundColor = '#f0f8ff';
    explainDiv.style.borderLeft = '4px solid #0d6efd';
    explainDiv.style.fontSize = '13px';
    explainDiv.style.lineHeight = '1.5';
    explainDiv.innerText = '💡 ' + currentQuestion.explanation;
  }
  
  await saveProgress();
}

async function toggleStar(uid){
  // 允许在所有模式下标星/取消标星（包括 wrong/star/random 模式）
  const r = await fetch('/api/star',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({uid, action:'toggle'})}).then(r=>r.json());
  // 更新本地缓存中的 global.star（用于即时 UI 反馈）
  ud_cache = ud_cache || {};
  ud_cache.global = ud_cache.global || {"wrong":[], "star":[]};
  if(r.starred){
    if(!ud_cache.global.star.includes(uid)) ud_cache.global.star.push(uid);
  } else {
    const idx = ud_cache.global.star.indexOf(uid); if(idx>=0) ud_cache.global.star.splice(idx,1);
  }
  setStarVisual(r.starred);
  // 保存进度（保持现有行为）
  await saveProgress();
}

function setStarVisual(state){
  const btn = document.getElementById('starBtn');
  if(!btn) return;
  if(state) btn.classList.add('starred'); else btn.classList.remove('starred');
}

function highlightList(){
  qlist.forEach((_,i)=>{
    const el = document.getElementById('li-'+i);
    if(!el) return;
    el.classList.remove('active');
    if(i===pos) el.classList.add('active');
  });
}

// 保存进度：位置与答题数据
async function saveProgress(){
  if(!progressKey) return;
  await fetch('/api/progress/save',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({key: progressKey, pos:pos})});
}

async function savePos(){
  if(!progressKey) return;
  await fetch('/api/progress/save',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({key: progressKey, pos:pos})});
}

window.onload = loadProgressList;
window.addEventListener('resize', ()=>{ adjustGridSize(); });
window.addEventListener('load', ()=>{ setTimeout(adjustGridSize, 80); });
