let qlist = []; let pos = 0; let mode = null;
let currentQuestion = null;
let multiSelected = new Set();

// 添加缺失的 toggleMultiOption 函数
function toggleMultiOption(key){
  if(multiSelected.has(key)) multiSelected.delete(key);
  else multiSelected.add(key);
  // 更新选项的视觉状态
  const btn = document.getElementById('opt-'+key);
  if(btn){
    if(multiSelected.has(key)) btn.classList.add('selected');
    else btn.classList.remove('selected');
  }
}

let revealMode = false;
let ud_cache = null; // 缓存用户数据
let progressKey = null; // 新变量：后端返回的进度键或 ud.current_progress_key
let explainMode = false; // 是否显示解析

async function loadProgressList(){
  // 先获取用户数据（包括 global、last_choice、progress）
  ud_cache = await fetch('/api/user/data').then(r=>r.json());
  // 获取当前的 flags
  const flags = await fetch('/api/flags').then(r=>r.json());
  explainMode = !!flags.show_explanations;
  
  // 优先使用后端记录的 current_progress_key
  progressKey = ud_cache.current_progress_key || null;
  const progObj = ud_cache.progress || {};
  if(!progressKey){
    const keys = Object.keys(progObj || {});
    if(keys.length>0){
      progressKey = keys[0];
    }
  }
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

  if(!qlist.length){
    document.getElementById('qtitle').innerText = '无题目，请返回面板重新开始';
    return;
  }
  // 先渲染列表，这样可以恢复上次的选择和答案显示
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
    // 根据 ud_cache 标注：last_choice / global.wrong / global.star
    if(ud_cache){
      const last = ud_cache.last_choice && ud_cache.last_choice[uid];
      const gl = ud_cache.global || {wrong:[], star:[]};
      if(last && last.correct) el.classList.add('green');
      else if(last && !last.correct) el.classList.add('red');
      if(gl.star && gl.star.includes(uid)) el.dataset.star = "1";
    }
    if(i===pos) el.classList.add('active');
    container.appendChild(el);
  });
  adjustGridSize(); // 确保渲染后调整尺寸与卡片宽度
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
  
  // 清除之前的解析显示
  const explainBox = document.getElementById('explanation-box');
  if(explainBox) explainBox.remove();

  // 使用缓存 ud_cache 判定 star 与 last_choice
  // 注意：错题练习（tag:wrong）和标星练习（tag:star）模式下，不读取 last_choice，始终允许答题
  const isTagMode = progressKey && (progressKey.startsWith('tag:'));
  const last = !isTagMode && ud_cache && ud_cache.last_choice ? ud_cache.last_choice[uid] : null;
  const gl = ud_cache && ud_cache.global ? ud_cache.global : {wrong:[], star:[]};
  setStarVisual(gl.star && gl.star.includes(uid));

  // 如果没有公开答案，但存在上次答题记录或背题模式，主动拉取正确答案用于渲染
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

  // 判断是否禁用交互：仅在背题模式时禁用；有上次记录时也允许答题但显示之前的选择
  const shouldDisable = revealMode;

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
    // 多选题：只要不在背题模式就显示提交按钮
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

  // 显示答案与解析的逻辑
  if(q.answer !== undefined && q.answer !== null){
    const optsArr = document.querySelectorAll('#opts .option-btn');
    optsArr.forEach(btn=>{
      const txt = btn.innerText.trim();
      const key = txt.split(/[.\s]/)[0];
      btn.classList.remove('correct','wrong','selected');
      
      if(revealMode){
        // 背题模式：直接显示正确答案（绿色），其他为红色
        if(Array.isArray(q.answer)){
          if(q.answer.includes(key)) btn.classList.add('correct');
          else btn.classList.add('wrong');
        } else {
          if(q.answer === key) btn.classList.add('correct');
          else btn.classList.add('wrong');
        }
      } else if(last){
        // 有上次答题记录：显示上次选择 + 对错标记
        if(Array.isArray(last.selected) && last.selected.includes(key)) btn.classList.add('selected');
        if(Array.isArray(q.answer)){
          if(q.answer.includes(key)) btn.classList.add('correct');
          if(Array.isArray(last.selected) && last.selected.includes(key) && !q.answer.includes(key)) btn.classList.add('wrong');
        } else {
          if(q.answer === key) btn.classList.add('correct');
          if(last.selected === key && last.selected !== q.answer) btn.classList.add('wrong');
        }
        // 在多选题中同步 multiSelected
        if(q.type === '多选题' && Array.isArray(last.selected)){
          multiSelected.clear();
          last.selected.forEach(k=>multiSelected.add(k));
        }
      }
    });

    // 更新方块颜色与反馈文字
    const square = document.getElementById('li-'+pos);
    if(square && (revealMode || last)){
      square.classList.remove('green','red');
      if(last){
        if(last.correct) square.classList.add('green'); else square.classList.add('red');
      }
    }

    // 显示反馈文字（仅在背题模式或有上次记录时）
    if(revealMode){
      // 背题模式：不显示反馈，仅显示解析
    } else if(last){
      document.getElementById('feedback').innerText = last.correct ? '✓ 回答正确' : ('✗ 回答错误，正确答案: ' + (Array.isArray(q.answer) ? JSON.stringify(q.answer) : q.answer));
    }

    // 显示解析（仅在背题模式或 explainMode 打开且有答题记录时）
    if((revealMode || (explainMode && last)) && q.explanation){
      const feedbackDiv = document.getElementById('feedback');
      const explainDiv = document.createElement('div');
      explainDiv.id = 'explanation-box';
      explainDiv.style.marginTop = '12px';
      explainDiv.style.padding = '10px';
      explainDiv.style.backgroundColor = '#f0f8ff';
      explainDiv.style.borderLeft = '4px solid #0d6efd';
      explainDiv.style.fontSize = '13px';
      explainDiv.style.lineHeight = '1.5';
      explainDiv.innerText = '💡 ' + q.explanation;
      feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
    }
  }

  document.getElementById('starBtn').onclick = ()=>toggleStar(uid);
  document.getElementById('nextBtn').onclick = ()=>{ pos = Math.min(pos+1, qlist.length-1); savePos(); loadQuestion(); };
  document.getElementById('prevBtn').onclick = ()=>{ pos = Math.max(pos-1, 0); savePos(); loadQuestion(); };
}

// 禁用所有选项按钮，不允许重新作答
function disableAllOptions(){
  const optsArr = document.querySelectorAll('#opts .option-btn');
  optsArr.forEach(btn=>{
    btn.disabled = true;
    btn.style.cursor = 'not-allowed';
    btn.style.opacity = '0.7';
  });
}

async function submitAnswerSingle(uid, selected){
  if(!currentQuestion) return;
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
  // 更新本地缓存
  ud_cache = ud_cache || {};
  ud_cache.last_choice = ud_cache.last_choice || {};
  ud_cache.last_choice[uid] = {"correct": r.correct, "selected": selected};
  ud_cache.global = ud_cache.global || {"wrong": [], "star": []};
  if(!r.correct){
    if(!ud_cache.global.wrong.includes(uid)) ud_cache.global.wrong.push(uid);
  } else {
    const idx = ud_cache.global.wrong.indexOf(uid); if(idx>=0) ud_cache.global.wrong.splice(idx,1);
  }
  // 更新方块颜色
  const square = document.getElementById('li-'+pos);
  if(square){ square.classList.remove('green','red'); if(r.correct) square.classList.add('green'); else square.classList.add('red'); }
  document.getElementById('feedback').innerText = r.correct ? '✓ 回答正确' : ('✗ 回答错误，正确答案: ' + JSON.stringify(r.answer));
  
  // 答题后禁用交互
  const optsArr = document.querySelectorAll('#opts .option-btn');
  optsArr.forEach(btn=>{ btn.onclick = null; btn.style.pointerEvents = 'none'; });
  
  // 答题后显示解析（若启用且题目有解析）
  if(explainMode && currentQuestion.explanation){
    const feedbackDiv = document.getElementById('feedback');
    const explainDiv = document.createElement('div');
    explainDiv.id = 'explanation-box';
    explainDiv.style.marginTop = '12px';
    explainDiv.style.padding = '10px';
    explainDiv.style.backgroundColor = '#f0f8ff';
    explainDiv.style.borderLeft = '4px solid #0d6efd';
    explainDiv.style.fontSize = '13px';
    explainDiv.style.lineHeight = '1.5';
    explainDiv.innerText = '💡 ' + currentQuestion.explanation;
    feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
  }
  
  // 立即保存进度到后端
  await saveProgress();
}

async function submitAnswerMulti(uid){
  if(!currentQuestion) return;
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
  // 更新本地缓存
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
  
  // 答题后禁用交互
  const optsArr = document.querySelectorAll('#opts .option-btn');
  optsArr.forEach(btn=>{ btn.onclick = null; btn.style.pointerEvents = 'none'; });
  
  // 答题后显示解析（若启用且题目有解析）
  if(explainMode && currentQuestion.explanation){
    const feedbackDiv = document.getElementById('feedback');
    const explainDiv = document.createElement('div');
    explainDiv.id = 'explanation-box';
    explainDiv.style.marginTop = '12px';
    explainDiv.style.padding = '10px';
    explainDiv.style.backgroundColor = '#f0f8ff';
    explainDiv.style.borderLeft = '4px solid #0d6efd';
    explainDiv.style.fontSize = '13px';
    explainDiv.style.lineHeight = '1.5';
    explainDiv.innerText = '💡 ' + currentQuestion.explanation;
    feedbackDiv.parentElement.insertBefore(explainDiv, feedbackDiv.nextSibling);
  }
  
  // 立即保存进度到后端
  await saveProgress();
}

async function toggleStar(uid){
  const r = await fetch('/api/star',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({uid, action:'toggle'})}).then(r=>r.json());
  // update cache global.star
  ud_cache = ud_cache || {};
  ud_cache.global = ud_cache.global || {"wrong":[], "star":[]};
  if(r.starred){
    if(!ud_cache.global.star.includes(uid)) ud_cache.global.star.push(uid);
  } else {
    const idx = ud_cache.global.star.indexOf(uid); if(idx>=0) ud_cache.global.star.splice(idx,1);
  }
  setStarVisual(r.starred);
  // 保存进度到后端
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
