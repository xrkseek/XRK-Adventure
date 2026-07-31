/**
 * 向日葵历险记 — 横板肉鸽原型
 * 验证问题：横板射击 + 清房选强化，是否好玩？
 */
(() => {
  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;

  // —— 调色（向日葵田野，避开紫/奶油陶土默认风）——
  const C = {
    skyA: "#4aa8cc",
    skyB: "#b7e4f2",
    hill: "#2f7a45",
    hillDark: "#246338",
    soil: "#7a5334",
    soilDark: "#5c3d26",
    petal: "#ffd54a",
    petalDeep: "#f0b429",
    center: "#6b3a1f",
    leaf: "#3d9b55",
    ink: "#1a241c",
    cream: "#fff6d6",
    danger: "#e85d4c",
    bug: "#7b5ea7",
    weed: "#5a8f3a",
    gold: "#ffe082",
    ui: "rgba(18,28,20,.82)",
  };

  // —— 输入 ——
  const keys = Object.create(null);
  let mouseDown = false;
  let mouseX = W / 2;
  let mouseY = H / 2;
  window.addEventListener("keydown", (e) => {
    keys[e.code] = true;
    if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.code)) e.preventDefault();
    if (e.code === "KeyR" && (state.mode === "dead" || state.mode === "win")) startRun();
    if (e.code === "Enter" || e.code === "Space") {
      if (state.mode === "title") startRun();
      if (state.mode === "dead" || state.mode === "win") startRun();
    }
  });
  window.addEventListener("keyup", (e) => { keys[e.code] = false; });
  canvas.addEventListener("mousedown", (e) => {
    mouseDown = true;
    updateMouse(e);
    if (state.mode === "title") startRun();
    if (state.mode === "upgrade") tryPickUpgrade(e);
    if (state.mode === "dead" || state.mode === "win") startRun();
  });
  window.addEventListener("mouseup", () => { mouseDown = false; });
  canvas.addEventListener("mousemove", updateMouse);
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());

  function updateMouse(e) {
    const r = canvas.getBoundingClientRect();
    mouseX = ((e.clientX - r.left) / r.width) * W;
    mouseY = ((e.clientY - r.top) / r.height) * H;
  }

  // —— 工具 ——
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];
  const aabb = (a, b) =>
    a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

  // —— 升级池 ——
  const UPGRADES = [
    { id: "dmg", name: "尖刺种子", desc: "伤害 +1", apply: (p) => { p.damage += 1; } },
    { id: "firerate", name: "连发花粉", desc: "射速加快", apply: (p) => { p.fireCdMax = Math.max(0.08, p.fireCdMax * 0.75); } },
    { id: "hp", name: "阳光滋养", desc: "最大生命 +1 并回满", apply: (p) => { p.maxHp += 1; p.hp = p.maxHp; } },
    { id: "speed", name: "风中摇摆", desc: "移速 +15%", apply: (p) => { p.speed *= 1.15; } },
    { id: "jump", name: "向阳腾跃", desc: "跳跃更高", apply: (p) => { p.jumpV *= 1.12; } },
    { id: "multi", name: "三叶齐射", desc: "一次射 3 发", apply: (p) => { p.spread = Math.min(5, p.spread + 2); } },
    { id: "pierce", name: "破壳钻心", desc: "子弹穿透 +1", apply: (p) => { p.pierce += 1; } },
    { id: "heal", name: "晨露回春", desc: "回复 2 点生命", apply: (p) => { p.hp = Math.min(p.maxHp, p.hp + 2); } },
  ];

  // —— 状态 ——
  const state = {
    mode: "title", // title | play | upgrade | dead | win
    floor: 1,
    maxFloor: 6,
    room: 0,
    roomsPerFloor: 3,
    seed: 0,
    kills: 0,
    time: 0,
    upgrades: [],
    choices: [],
    shake: 0,
    hitstop: 0,
    particles: [],
    floats: [],
    camX: 0,
  };

  let player, platforms, enemies, bullets, enemyBullets, roomW, door;

  function makePlayer() {
    return {
      x: 80, y: 200, w: 28, h: 40,
      vx: 0, vy: 0,
      facing: 1,
      onGround: false,
      coyote: 0,
      jumpBuf: 0,
      hp: 5, maxHp: 5,
      speed: 220,
      jumpV: -460,
      fireCd: 0, fireCdMax: 0.22,
      damage: 1,
      spread: 1,
      pierce: 0,
      invuln: 0,
      squash: 1,
      stretch: 1,
      anim: 0,
    };
  }

  function startRun() {
    state.mode = "play";
    state.floor = 1;
    state.room = 0;
    state.kills = 0;
    state.time = 0;
    state.upgrades = [];
    state.seed = (Math.random() * 1e9) | 0;
    state.shake = 0;
    state.hitstop = 0;
    state.particles = [];
    state.floats = [];
    player = makePlayer();
    buildRoom();
  }

  function buildRoom() {
    const rng = mulberry32(state.seed + state.floor * 97 + state.room * 13);
    roomW = 1100 + state.floor * 40;
    platforms = [];
    enemies = [];
    bullets = [];
    enemyBullets = [];
    door = null;

    // 地面
    platforms.push({ x: 0, y: H - 70, w: roomW, h: 80, ground: true });

    // 浮台
    const plats = 4 + ((rng() * 3) | 0) + Math.floor(state.floor / 2);
    for (let i = 0; i < plats; i++) {
      const pw = 90 + rng() * 140;
      const px = 160 + rng() * (roomW - 320 - pw);
      const py = 160 + rng() * 220;
      platforms.push({ x: px, y: py, w: pw, h: 18 });
    }

    // 敌人数量随层数
    const count = 3 + state.floor + ((rng() * 2) | 0);
    const isBoss = state.floor >= state.maxFloor && state.room === state.roomsPerFloor - 1;

    if (isBoss) {
      enemies.push(makeEnemy("boss", roomW * 0.55, H - 70 - 70, rng));
    } else {
      for (let i = 0; i < count; i++) {
        const type = rng() < 0.55 ? "bug" : rng() < 0.7 ? "weed" : "flyer";
        const ex = 280 + rng() * (roomW - 400);
        const ey = type === "flyer" ? 120 + rng() * 160 : H - 70 - 36;
        enemies.push(makeEnemy(type, ex, ey, rng));
      }
    }

    player.x = 70;
    player.y = H - 70 - player.h - 2;
    player.vx = 0;
    player.vy = 0;
    player.invuln = 0.6;
    state.camX = 0;
  }

  function makeEnemy(type, x, y, rng) {
    const scale = 1 + (state.floor - 1) * 0.12;
    if (type === "bug") {
      return {
        type, x, y, w: 34, h: 28,
        vx: (rng() < 0.5 ? -1 : 1) * (60 + rng() * 40) * (0.9 + scale * 0.1),
        vy: 0, hp: Math.ceil(2 * scale), maxHp: Math.ceil(2 * scale),
        damage: 1, flash: 0, shootCd: 0, bob: rng() * Math.PI * 2,
      };
    }
    if (type === "weed") {
      return {
        type, x, y: y - 10, w: 30, h: 46,
        vx: 0, vy: 0, hp: Math.ceil(3 * scale), maxHp: Math.ceil(3 * scale),
        damage: 1, flash: 0, shootCd: 1.2 + rng(), bob: 0, rooted: true,
      };
    }
    if (type === "flyer") {
      return {
        type, x, y, w: 30, h: 24,
        vx: (rng() < 0.5 ? -1 : 1) * 80, vy: 0,
        hp: Math.ceil(2 * scale), maxHp: Math.ceil(2 * scale),
        damage: 1, flash: 0, shootCd: 0.8 + rng(), bob: rng() * 10, baseY: y,
      };
    }
    // boss
    return {
      type: "boss", x, y, w: 70, h: 70,
      vx: 40, vy: 0,
      hp: Math.ceil(28 + state.floor * 4), maxHp: Math.ceil(28 + state.floor * 4),
      damage: 2, flash: 0, shootCd: 0.6, bob: 0, phase: 0,
    };
  }

  function mulberry32(a) {
    return function () {
      let t = (a += 0x6d2b79f5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // —— 粒子 / 飘字 ——
  function burst(x, y, color, n = 10, speed = 180) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = rand(speed * 0.3, speed);
      state.particles.push({
        x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 40,
        life: rand(0.3, 0.7), max: 0.7, r: rand(2, 5), color, g: 500,
      });
    }
  }

  function floatText(x, y, text, color = C.cream) {
    state.floats.push({ x, y, text, color, life: 0.8 });
  }

  function addShake(a) { state.shake = Math.min(1, state.shake + a); }
  function addHitstop(t) { state.hitstop = Math.max(state.hitstop, t); }

  // —— 升级 ——
  function offerUpgrades() {
    const pool = UPGRADES.slice();
    const choices = [];
    for (let i = 0; i < 3 && pool.length; i++) {
      const idx = (Math.random() * pool.length) | 0;
      choices.push(pool.splice(idx, 1)[0]);
    }
    state.choices = choices;
    state.mode = "upgrade";
  }

  function tryPickUpgrade(e) {
    const r = canvas.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    const my = ((e.clientY - r.top) / r.height) * H;
    const cards = getUpgradeCards();
    for (let i = 0; i < cards.length; i++) {
      const c = cards[i];
      if (mx >= c.x && mx <= c.x + c.w && my >= c.y && my <= c.y + c.h) {
        applyUpgrade(state.choices[i]);
        return;
      }
    }
  }

  function getUpgradeCards() {
    const cw = 200, ch = 160, gap = 24;
    const total = state.choices.length * cw + (state.choices.length - 1) * gap;
    const sx = (W - total) / 2;
    const sy = H / 2 - ch / 2 + 10;
    return state.choices.map((_, i) => ({ x: sx + i * (cw + gap), y: sy, w: cw, h: ch }));
  }

  function applyUpgrade(u) {
    u.apply(player);
    state.upgrades.push(u.name);
    burst(W / 2, H / 2, C.petal, 20, 260);
    addShake(0.25);
    advanceRoom();
  }

  function advanceRoom() {
    state.mode = "play";
    state.room++;
    if (state.room >= state.roomsPerFloor) {
      state.room = 0;
      state.floor++;
      if (state.floor > state.maxFloor) {
        state.mode = "win";
        return;
      }
    }
    buildRoom();
  }

  function openDoor() {
    door = { x: roomW - 90, y: H - 70 - 90, w: 50, h: 90, open: true };
  }

  // —— 射击 ——
  function tryShoot(dt) {
    if (player.fireCd > 0) player.fireCd -= dt;
    const want =
      keys.KeyJ || keys.KeyZ || keys.KeyK || mouseDown;
    if (!want || player.fireCd > 0) return;
    player.fireCd = player.fireCdMax;

    const cx = player.x + player.w / 2;
    const cy = player.y + player.h * 0.35;
    let aimX = mouseX + state.camX - cx;
    let aimY = mouseY - cy;
    if (!mouseDown && !keys.KeyJ && !keys.KeyZ) {
      aimX = player.facing;
      aimY = 0;
    }
    const len = Math.hypot(aimX, aimY) || 1;
    aimX /= len;
    aimY /= len;
    player.facing = aimX >= 0 ? 1 : -1;

    const n = player.spread;
    const spreadAng = n > 1 ? 0.18 : 0;
    for (let i = 0; i < n; i++) {
      const t = n === 1 ? 0 : (i / (n - 1) - 0.5) * 2;
      const ang = Math.atan2(aimY, aimX) + t * spreadAng;
      bullets.push({
        x: cx, y: cy, r: 5,
        vx: Math.cos(ang) * 520,
        vy: Math.sin(ang) * 520,
        life: 1.2,
        damage: player.damage,
        pierce: player.pierce,
        hit: new Set(),
      });
    }
    burst(cx + aimX * 16, cy + aimY * 16, C.petalDeep, 4, 80);
  }

  // —— 物理 ——
  function updatePlayer(dt) {
    const p = player;
    p.anim += dt;
    if (p.invuln > 0) p.invuln -= dt;

    let input = 0;
    if (keys.KeyA || keys.ArrowLeft) input -= 1;
    if (keys.KeyD || keys.ArrowRight) input += 1;
    if (input) p.facing = input;

    const target = input * p.speed;
    const accel = p.onGround ? 2400 : 1400;
    if (Math.abs(target) > Math.abs(p.vx) || Math.sign(target) !== Math.sign(p.vx)) {
      p.vx = moveToward(p.vx, target, accel * dt);
    } else {
      p.vx = moveToward(p.vx, target, (p.onGround ? 2800 : 800) * dt);
    }

    // gravity
    p.vy += 1400 * dt;
    if (p.vy > 900) p.vy = 900;

    // coyote / buffer
    if (p.onGround) p.coyote = 0.1;
    else p.coyote = Math.max(0, p.coyote - dt);

    if (keys.Space || keys.KeyW || keys.ArrowUp) {
      if (!p._jumpHeld) p.jumpBuf = 0.14;
      p._jumpHeld = true;
    } else {
      p._jumpHeld = false;
      // variable jump
      if (p.vy < -120) p.vy *= 0.55;
    }
    p.jumpBuf = Math.max(0, p.jumpBuf - dt);

    if (p.jumpBuf > 0 && p.coyote > 0) {
      p.vy = p.jumpV;
      p.coyote = 0;
      p.jumpBuf = 0;
      p.onGround = false;
      p.squash = 0.72;
      p.stretch = 1.28;
      burst(p.x + p.w / 2, p.y + p.h, C.cream, 6, 90);
    }

    // move X
    p.x += p.vx * dt;
    resolveSolid(p, true);
    // move Y
    p.y += p.vy * dt;
    p.onGround = false;
    resolveSolid(p, false);

    // squash settle
    p.squash = lerp(p.squash, 1, 1 - Math.pow(0.001, dt));
    p.stretch = lerp(p.stretch, 1, 1 - Math.pow(0.001, dt));

    // bounds
    p.x = clamp(p.x, 0, roomW - p.w);
    if (p.y > H + 80) damagePlayer(99);

    tryShoot(dt);

    // door
    if (door && door.open && aabb(p, door)) {
      offerUpgrades();
    }
  }

  function moveToward(cur, target, maxDelta) {
    if (Math.abs(target - cur) <= maxDelta) return target;
    return cur + Math.sign(target - cur) * maxDelta;
  }

  function resolveSolid(p, isX) {
    for (const pl of platforms) {
      if (!aabb(p, pl)) continue;
      if (isX) {
        if (p.vx > 0) p.x = pl.x - p.w;
        else if (p.vx < 0) p.x = pl.x + pl.w;
        p.vx = 0;
      } else {
        if (p.vy > 0) {
          p.y = pl.y - p.h;
          p.vy = 0;
          if (!p.onGround) {
            p.squash = 1.25;
            p.stretch = 0.8;
          }
          p.onGround = true;
        } else if (p.vy < 0) {
          p.y = pl.y + pl.h;
          p.vy = 0;
        }
      }
    }
  }

  function damagePlayer(amount) {
    if (player.invuln > 0) return;
    player.hp -= amount;
    player.invuln = 1.0;
    player.vy = -220;
    addShake(0.45);
    addHitstop(0.06);
    burst(player.x + player.w / 2, player.y + player.h / 2, C.danger, 14, 200);
    if (player.hp <= 0) {
      player.hp = 0;
      state.mode = "dead";
      burst(player.x + player.w / 2, player.y + player.h / 2, C.petal, 30, 280);
    }
  }

  function updateEnemies(dt) {
    for (const e of enemies) {
      e.flash = Math.max(0, e.flash - dt);
      e.bob += dt;

      if (e.type === "bug") {
        e.x += e.vx * dt;
        // 平台边缘掉头
        const foot = { x: e.x + (e.vx > 0 ? e.w + 2 : -6), y: e.y + e.h + 2, w: 4, h: 4 };
        let onEdge = true;
        for (const pl of platforms) if (aabb(foot, pl)) onEdge = false;
        if (onEdge || e.x < 40 || e.x + e.w > roomW - 40) e.vx *= -1;
        // 简易落地
        e.vy += 1400 * dt;
        e.y += e.vy * dt;
        for (const pl of platforms) {
          if (aabb(e, pl) && e.vy >= 0) {
            e.y = pl.y - e.h;
            e.vy = 0;
          }
        }
      } else if (e.type === "flyer") {
        e.x += e.vx * dt;
        e.y = e.baseY + Math.sin(e.bob * 2.2) * 28;
        if (e.x < 60 || e.x > roomW - 90) e.vx *= -1;
        e.shootCd -= dt;
        if (e.shootCd <= 0) {
          e.shootCd = 1.6;
          const cx = e.x + e.w / 2, cy = e.y + e.h / 2;
          const dx = player.x + player.w / 2 - cx;
          const dy = player.y + player.h / 2 - cy;
          const len = Math.hypot(dx, dy) || 1;
          enemyBullets.push({
            x: cx, y: cy, r: 6,
            vx: (dx / len) * 180, vy: (dy / len) * 180, life: 3, damage: 1,
          });
        }
      } else if (e.type === "weed") {
        e.shootCd -= dt;
        if (e.shootCd <= 0) {
          e.shootCd = 1.8;
          const dir = Math.sign(player.x - e.x) || 1;
          enemyBullets.push({
            x: e.x + e.w / 2, y: e.y + 16, r: 5,
            vx: dir * 220, vy: -80, life: 2.5, damage: 1, g: 400,
          });
        }
      } else if (e.type === "boss") {
        e.phase += dt;
        e.x += e.vx * dt;
        if (e.x < 100 || e.x > roomW - 160) e.vx *= -1;
        e.shootCd -= dt;
        if (e.shootCd <= 0) {
          e.shootCd = e.hp < e.maxHp * 0.4 ? 0.35 : 0.7;
          const cx = e.x + e.w / 2, cy = e.y + e.h / 2;
          const n = 5;
          for (let i = 0; i < n; i++) {
            const ang = (i / n) * Math.PI * 2 + e.phase;
            enemyBullets.push({
              x: cx, y: cy, r: 7,
              vx: Math.cos(ang) * 160, vy: Math.sin(ang) * 160,
              life: 4, damage: 1,
            });
          }
        }
      }

      // 接触伤害
      if (aabb(player, e) && player.invuln <= 0) {
        damagePlayer(e.damage);
        player.vx = Math.sign(player.x - e.x) * 280;
      }
    }
  }

  function updateBullets(dt) {
    for (const b of bullets) {
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      b.life -= dt;
      for (const e of enemies) {
        if (b.hit.has(e)) continue;
        if (circleRect(b.x, b.y, b.r, e)) {
          b.hit.add(e);
          e.hp -= b.damage;
          e.flash = 0.12;
          floatText(e.x + e.w / 2, e.y, `-${b.damage}`, C.gold);
          burst(b.x, b.y, C.petal, 6, 120);
          addShake(0.12);
          addHitstop(0.03);
          if (e.hp <= 0) {
            state.kills++;
            burst(e.x + e.w / 2, e.y + e.h / 2, e.type === "boss" ? C.danger : C.bug, 18, 240);
            addShake(0.35);
            e.dead = true;
          }
          if (b.pierce <= 0) { b.life = 0; break; }
          b.pierce--;
        }
      }
    }
    bullets = bullets.filter((b) => b.life > 0 && b.x > -40 && b.x < roomW + 40 && b.y > -40 && b.y < H + 40);
    enemies = enemies.filter((e) => !e.dead);

    if (enemies.length === 0 && !door) openDoor();

    for (const b of enemyBullets) {
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      if (b.g) b.vy += b.g * dt;
      b.life -= dt;
      if (circleRect(b.x, b.y, b.r, player) && player.invuln <= 0) {
        damagePlayer(b.damage);
        b.life = 0;
      }
    }
    enemyBullets = enemyBullets.filter((b) => b.life > 0);
  }

  function circleRect(cx, cy, r, rect) {
    const nx = clamp(cx, rect.x, rect.x + rect.w);
    const ny = clamp(cy, rect.y, rect.y + rect.h);
    const dx = cx - nx, dy = cy - ny;
    return dx * dx + dy * dy <= r * r;
  }

  function updateFx(dt) {
    state.shake = Math.max(0, state.shake - dt * 1.6);
    for (const p of state.particles) {
      p.vy += (p.g || 0) * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.life -= dt;
    }
    state.particles = state.particles.filter((p) => p.life > 0);
    for (const f of state.floats) {
      f.y -= 40 * dt;
      f.life -= dt;
    }
    state.floats = state.floats.filter((f) => f.life > 0);

    // camera
    const target = clamp(player.x - W * 0.35, 0, Math.max(0, roomW - W));
    state.camX = lerp(state.camX, target, 1 - Math.pow(0.0008, dt));
  }

  // —— 绘制 ——
  function draw() {
    const trauma = state.shake * state.shake;
    const ox = (Math.random() - 0.5) * 18 * trauma;
    const oy = (Math.random() - 0.5) * 14 * trauma;

    ctx.save();
    ctx.translate(ox - state.camX, oy);

    drawBackground();
    for (const pl of platforms) drawPlatform(pl);
    if (door) drawDoor(door);
    for (const e of enemies) drawEnemy(e);
    for (const b of enemyBullets) {
      ctx.fillStyle = C.danger;
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
      ctx.fill();
    }
    for (const b of bullets) drawSeed(b);
    if (state.mode !== "dead") drawPlayer(player);
    for (const p of state.particles) {
      ctx.globalAlpha = clamp(p.life / p.max, 0, 1);
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }
    for (const f of state.floats) {
      ctx.globalAlpha = clamp(f.life / 0.8, 0, 1);
      ctx.fillStyle = f.color;
      ctx.font = "700 16px 'Noto Sans SC', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(f.text, f.x, f.y);
      ctx.globalAlpha = 1;
    }

    ctx.restore();

    if (state.mode === "play" || state.mode === "upgrade") drawHUD();
    if (state.mode === "title") drawTitle();
    if (state.mode === "upgrade") drawUpgradeUI();
    if (state.mode === "dead") drawEnd(false);
    if (state.mode === "win") drawEnd(true);
  }

  function drawBackground() {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, C.skyA);
    g.addColorStop(1, C.skyB);
    ctx.fillStyle = g;
    ctx.fillRect(state.camX - 20, -20, W + 40, H + 40);

    // 太阳
    ctx.fillStyle = C.petal;
    ctx.beginPath();
    ctx.arc(state.camX + W - 120, 70, 36, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 0.25;
    ctx.beginPath();
    ctx.arc(state.camX + W - 120, 70, 58, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // 远山
    ctx.fillStyle = C.hillDark;
    drawHills(state.camX * 0.3, H - 140, 1.2);
    ctx.fillStyle = C.hill;
    drawHills(state.camX * 0.55, H - 100, 0.9);
  }

  function drawHills(off, baseY, scale) {
    ctx.beginPath();
    ctx.moveTo(state.camX - 40, H);
    for (let x = -40; x <= W + 80; x += 40) {
      const wx = state.camX + x;
      const y = baseY + Math.sin((wx + off) * 0.008 * scale) * 28 * scale
        + Math.sin((wx + off) * 0.02) * 10;
      ctx.lineTo(wx, y);
    }
    ctx.lineTo(state.camX + W + 40, H);
    ctx.closePath();
    ctx.fill();
  }

  function drawPlatform(pl) {
    if (pl.ground) {
      ctx.fillStyle = C.soil;
      ctx.fillRect(pl.x, pl.y, pl.w, pl.h);
      ctx.fillStyle = C.hill;
      ctx.fillRect(pl.x, pl.y, pl.w, 14);
      // 草尖
      ctx.strokeStyle = C.leaf;
      ctx.lineWidth = 2;
      for (let x = pl.x; x < pl.x + pl.w; x += 18) {
        const sway = Math.sin(state.time * 3 + x * 0.05) * 2;
        ctx.beginPath();
        ctx.moveTo(x, pl.y + 2);
        ctx.quadraticCurveTo(x + sway, pl.y - 8, x + 3 + sway, pl.y - 14);
        ctx.stroke();
      }
    } else {
      ctx.fillStyle = C.soilDark;
      ctx.fillRect(pl.x, pl.y, pl.w, pl.h);
      ctx.fillStyle = C.hill;
      ctx.fillRect(pl.x, pl.y, pl.w, 6);
      ctx.fillStyle = "rgba(255,255,255,.15)";
      ctx.fillRect(pl.x, pl.y, pl.w, 2);
    }
  }

  function drawDoor(d) {
    const pulse = 0.5 + Math.sin(state.time * 4) * 0.5;
    ctx.fillStyle = `rgba(255,213,74,${0.15 + pulse * 0.2})`;
    ctx.fillRect(d.x - 8, d.y - 8, d.w + 16, d.h + 16);
    ctx.fillStyle = C.center;
    ctx.fillRect(d.x, d.y, d.w, d.h);
    ctx.fillStyle = C.petal;
    ctx.beginPath();
    ctx.arc(d.x + d.w / 2, d.y + 28, 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = C.center;
    ctx.beginPath();
    ctx.arc(d.x + d.w / 2, d.y + 28, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = C.cream;
    ctx.font = "700 12px 'Noto Sans SC'";
    ctx.textAlign = "center";
    ctx.fillText("下一关", d.x + d.w / 2, d.y - 10);
  }

  function drawPlayer(p) {
    const cx = p.x + p.w / 2;
    const cy = p.y + p.h / 2;
    const blink = p.invuln > 0 && Math.floor(p.invuln * 12) % 2 === 0;
    if (blink) return;

    ctx.save();
    ctx.translate(cx, cy + p.h * 0.15);
    ctx.scale(p.facing * p.stretch, p.squash);

    // 茎
    ctx.strokeStyle = C.leaf;
    ctx.lineWidth = 5;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(0, 8);
    ctx.lineTo(0, 22);
    ctx.stroke();

    // 叶
    ctx.fillStyle = C.leaf;
    ctx.beginPath();
    ctx.ellipse(-10, 14, 8, 4, -0.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(10, 16, 8, 4, 0.5, 0, Math.PI * 2);
    ctx.fill();

    // 花瓣
    const bob = Math.sin(p.anim * 6) * 1.5;
    ctx.translate(0, -6 + bob);
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2 + p.anim * 0.4;
      ctx.fillStyle = i % 2 ? C.petal : C.petalDeep;
      ctx.beginPath();
      ctx.ellipse(Math.cos(a) * 12, Math.sin(a) * 12, 7, 4, a, 0, Math.PI * 2);
      ctx.fill();
    }
    // 花心
    ctx.fillStyle = C.center;
    ctx.beginPath();
    ctx.arc(0, 0, 9, 0, Math.PI * 2);
    ctx.fill();
    // 脸
    ctx.fillStyle = C.cream;
    ctx.beginPath();
    ctx.arc(-3.5, -1, 1.6, 0, Math.PI * 2);
    ctx.arc(3.5, -1, 1.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = C.cream;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(0, 2, 3, 0.15, Math.PI - 0.15);
    ctx.stroke();

    ctx.restore();
  }

  function drawSeed(b) {
    ctx.save();
    ctx.translate(b.x, b.y);
    ctx.rotate(Math.atan2(b.vy, b.vx));
    ctx.fillStyle = C.center;
    ctx.beginPath();
    ctx.ellipse(0, 0, 7, 3.5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = C.petal;
    ctx.beginPath();
    ctx.ellipse(-2, 0, 3, 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawEnemy(e) {
    const flash = e.flash > 0;
    ctx.save();
    if (flash) ctx.globalAlpha = 0.5;

    if (e.type === "bug") {
      ctx.fillStyle = C.bug;
      ctx.beginPath();
      ctx.ellipse(e.x + e.w / 2, e.y + e.h / 2, e.w / 2, e.h / 2, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = C.ink;
      ctx.fillRect(e.x + 8, e.y + 8, 4, 4);
      ctx.fillRect(e.x + e.w - 14, e.y + 8, 4, 4);
      // 腿
      ctx.strokeStyle = C.ink;
      ctx.lineWidth = 2;
      for (let i = 0; i < 3; i++) {
        const lx = e.x + 8 + i * 8;
        ctx.beginPath();
        ctx.moveTo(lx, e.y + e.h - 4);
        ctx.lineTo(lx - 4, e.y + e.h + 4);
        ctx.stroke();
      }
    } else if (e.type === "weed") {
      ctx.fillStyle = C.weed;
      ctx.fillRect(e.x + e.w / 2 - 4, e.y + 10, 8, e.h - 10);
      ctx.beginPath();
      ctx.moveTo(e.x + e.w / 2, e.y);
      ctx.lineTo(e.x, e.y + 22);
      ctx.lineTo(e.x + e.w, e.y + 22);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = C.danger;
      ctx.beginPath();
      ctx.arc(e.x + e.w / 2, e.y + 18, 5, 0, Math.PI * 2);
      ctx.fill();
    } else if (e.type === "flyer") {
      ctx.fillStyle = "#e8a0b8";
      const flap = Math.sin(e.bob * 12) * 6;
      ctx.beginPath();
      ctx.ellipse(e.x + 4, e.y + 12, 10, 4 + flap * 0.2, -0.4, 0, Math.PI * 2);
      ctx.ellipse(e.x + e.w - 4, e.y + 12, 10, 4 + flap * 0.2, 0.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#c45c7a";
      ctx.beginPath();
      ctx.ellipse(e.x + e.w / 2, e.y + e.h / 2, 10, 8, 0, 0, Math.PI * 2);
      ctx.fill();
    } else if (e.type === "boss") {
      // 巨型枯萎向日葵
      const cx = e.x + e.w / 2, cy = e.y + e.h / 2;
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * Math.PI * 2 + state.time;
        ctx.fillStyle = i % 2 ? "#8b4518" : "#a0522d";
        ctx.beginPath();
        ctx.ellipse(cx + Math.cos(a) * 28, cy + Math.sin(a) * 28, 14, 7, a, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#2b1810";
      ctx.beginPath();
      ctx.arc(cx, cy, 20, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = C.danger;
      ctx.beginPath();
      ctx.arc(cx - 7, cy - 2, 3, 0, Math.PI * 2);
      ctx.arc(cx + 7, cy - 2, 3, 0, Math.PI * 2);
      ctx.fill();
      // HP bar
      const bw = 80, ratio = e.hp / e.maxHp;
      ctx.fillStyle = "rgba(0,0,0,.5)";
      ctx.fillRect(cx - bw / 2, e.y - 16, bw, 8);
      ctx.fillStyle = C.danger;
      ctx.fillRect(cx - bw / 2, e.y - 16, bw * ratio, 8);
    }

    // 小血条
    if (e.type !== "boss" && e.hp < e.maxHp) {
      const ratio = e.hp / e.maxHp;
      ctx.globalAlpha = 1;
      ctx.fillStyle = "rgba(0,0,0,.45)";
      ctx.fillRect(e.x, e.y - 8, e.w, 4);
      ctx.fillStyle = C.danger;
      ctx.fillRect(e.x, e.y - 8, e.w * ratio, 4);
    }

    ctx.restore();
  }

  function drawHUD() {
    // 顶栏
    ctx.fillStyle = C.ui;
    ctx.fillRect(0, 0, W, 44);

    // 生命（花瓣）
    for (let i = 0; i < player.maxHp; i++) {
      const x = 18 + i * 26;
      const y = 22;
      ctx.fillStyle = i < player.hp ? C.petal : "rgba(255,255,255,.15)";
      ctx.beginPath();
      ctx.arc(x, y, 9, 0, Math.PI * 2);
      ctx.fill();
      if (i < player.hp) {
        ctx.fillStyle = C.center;
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    ctx.fillStyle = C.cream;
    ctx.font = "700 14px 'Noto Sans SC'";
    ctx.textAlign = "left";
    ctx.fillText(`第 ${state.floor} 层 · 房间 ${state.room + 1}/${state.roomsPerFloor}`, 18 + player.maxHp * 26 + 12, 28);

    ctx.textAlign = "right";
    ctx.fillText(`击杀 ${state.kills}`, W - 18, 28);

    if (door && state.mode === "play") {
      ctx.textAlign = "center";
      ctx.fillStyle = C.petal;
      ctx.font = "700 13px 'Noto Sans SC'";
      ctx.fillText("▶ 走进阳光之门", W / 2, H - 18);
    }
  }

  function drawTitle() {
    ctx.fillStyle = "rgba(10,18,12,.55)";
    ctx.fillRect(0, 0, W, H);

    ctx.textAlign = "center";
    ctx.fillStyle = C.petal;
    ctx.font = "400 56px 'ZCOOL KuaiLe', sans-serif";
    ctx.fillText("向日葵历险记", W / 2, H * 0.38);

    ctx.fillStyle = C.cream;
    ctx.font = "500 16px 'Noto Sans SC'";
    ctx.fillText("横板肉鸽原型 · 清房 · 选强化 · 死了重开", W / 2, H * 0.38 + 42);

    const pulse = 0.65 + Math.sin(state.time * 3) * 0.35;
    ctx.globalAlpha = pulse;
    ctx.fillStyle = C.accent || "#ff8a3d";
    ctx.font = "700 18px 'Noto Sans SC'";
    ctx.fillText("点击或按 Enter 开始冒险", W / 2, H * 0.62);
    ctx.globalAlpha = 1;

    ctx.fillStyle = "rgba(255,255,255,.55)";
    ctx.font = "12px 'Noto Sans SC'";
    ctx.fillText("A/D 移动 · 空格跳跃 · J / 鼠标射击", W / 2, H * 0.72);
  }

  function drawUpgradeUI() {
    ctx.fillStyle = "rgba(10,18,12,.72)";
    ctx.fillRect(0, 0, W, H);

    ctx.textAlign = "center";
    ctx.fillStyle = C.petal;
    ctx.font = "400 36px 'ZCOOL KuaiLe', sans-serif";
    ctx.fillText("阳光祝福", W / 2, 100);
    ctx.fillStyle = C.cream;
    ctx.font = "500 14px 'Noto Sans SC'";
    ctx.fillText("选择一项强化，继续向阳生长", W / 2, 132);

    const cards = getUpgradeCards();
    cards.forEach((card, i) => {
      const u = state.choices[i];
      const hover =
        mouseX >= card.x && mouseX <= card.x + card.w &&
        mouseY >= card.y && mouseY <= card.y + card.h;

      ctx.fillStyle = hover ? "rgba(255,213,74,.2)" : "rgba(255,246,214,.08)";
      roundRect(card.x, card.y, card.w, card.h, 12);
      ctx.fill();
      ctx.strokeStyle = hover ? C.petal : "rgba(255,255,255,.25)";
      ctx.lineWidth = 2;
      roundRect(card.x, card.y, card.w, card.h, 12);
      ctx.stroke();

      ctx.fillStyle = C.petal;
      ctx.font = "700 18px 'Noto Sans SC'";
      ctx.fillText(u.name, card.x + card.w / 2, card.y + 58);
      ctx.fillStyle = C.cream;
      ctx.font = "500 14px 'Noto Sans SC'";
      ctx.fillText(u.desc, card.x + card.w / 2, card.y + 92);
      ctx.fillStyle = "rgba(255,255,255,.45)";
      ctx.font = "12px 'Noto Sans SC'";
      ctx.fillText("点击选择", card.x + card.w / 2, card.y + 130);
    });
  }

  function drawEnd(win) {
    ctx.fillStyle = "rgba(10,18,12,.75)";
    ctx.fillRect(0, 0, W, H);
    ctx.textAlign = "center";
    ctx.fillStyle = win ? C.petal : C.danger;
    ctx.font = "400 48px 'ZCOOL KuaiLe', sans-serif";
    ctx.fillText(win ? "向阳绽放！" : "枯萎了…", W / 2, H * 0.36);
    ctx.fillStyle = C.cream;
    ctx.font = "500 16px 'Noto Sans SC'";
    ctx.fillText(
      `到达第 ${Math.min(state.floor, state.maxFloor)} 层 · 击杀 ${state.kills} · 强化 ${state.upgrades.length} 项`,
      W / 2,
      H * 0.36 + 44
    );
    if (state.upgrades.length) {
      ctx.fillStyle = "rgba(255,255,255,.55)";
      ctx.font = "12px 'Noto Sans SC'";
      ctx.fillText(state.upgrades.join(" · "), W / 2, H * 0.36 + 72);
    }
    ctx.fillStyle = C.petal;
    ctx.font = "700 18px 'Noto Sans SC'";
    ctx.fillText("按 R / Enter / 点击 再开一局", W / 2, H * 0.68);
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // —— 主循环 ——
  let last = performance.now();
  function frame(now) {
    let dt = Math.min(0.033, (now - last) / 1000);
    last = now;
    state.time += dt;

    if (state.hitstop > 0) {
      state.hitstop -= dt;
      dt *= 0.15;
    }

    if (state.mode === "play") {
      updatePlayer(dt);
      updateEnemies(dt);
      updateBullets(dt);
      updateFx(dt);
    } else if (state.mode === "title" || state.mode === "upgrade" || state.mode === "dead" || state.mode === "win") {
      // 轻量粒子漂浮
      if (Math.random() < 0.2) {
        state.particles.push({
          x: state.camX + rand(0, W),
          y: H + 10,
          vx: rand(-20, 20),
          vy: rand(-80, -40),
          life: 1.5,
          max: 1.5,
          r: rand(2, 4),
          color: C.petal,
          g: 0,
        });
      }
      for (const p of state.particles) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.life -= dt;
      }
      state.particles = state.particles.filter((p) => p.life > 0);
    }

    draw();
    requestAnimationFrame(frame);
  }

  // 标题页也需要 player 占位供 HUD 安全
  player = makePlayer();
  platforms = [{ x: 0, y: H - 70, w: W, h: 80, ground: true }];
  enemies = [];
  bullets = [];
  enemyBullets = [];
  roomW = W;
  door = null;

  requestAnimationFrame(frame);
})();
