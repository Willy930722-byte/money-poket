<!DOCTYPE html>
<html lang="zh-Hant" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>台灣指數優先・多維度下鑽看盤終端 | TAIEX & OTC Pro Terminal</title>
  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Google Fonts: Inter, Noto Sans TC, JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700;900&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            terminal: {
              bg: '#0a0d12',
              panel: '#121722',
              panelHover: '#192030',
              border: '#262d3d',
              muted: '#848e9c',
              text: '#e2e8f0',
              accent: '#3b82f6',
              twRed: '#ef4444',
              twGreen: '#10b981'
            }
          },
          fontFamily: {
            sans: ['"Inter"', '"Noto Sans TC"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace']
          }
        }
      }
    };
  </script>
  <style>
    body {
      background-color: #0a0d12;
      color: #e2e8f0;
      font-family: 'Inter', 'Noto Sans TC', sans-serif;
      overflow-x: hidden;
    }
    .tabular-nums {
      font-variant-numeric: tabular-nums;
      font-family: 'JetBrains Mono', 'Noto Sans TC', monospace;
    }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0a0d12; }
    ::-webkit-scrollbar-thumb { background: #262d3d; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }

    /* 台股紅漲綠跌跳動閃爍動畫 */
    @keyframes flashRed {
      0% { background-color: rgba(239, 68, 68, 0.35); }
      100% { background-color: transparent; }
    }
    @keyframes flashGreen {
      0% { background-color: rgba(16, 185, 129, 0.35); }
      100% { background-color: transparent; }
    }
    .flash-up { animation: flashRed 0.6s ease-out; }
    .flash-down { animation: flashGreen 0.6s ease-out; }

    canvas.interactive-chart {
      cursor: crosshair;
      touch-action: none;
    }
    canvas.interactive-chart.grabbing {
      cursor: grabbing;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col selection:bg-red-500/30 selection:text-white">

  <!-- ==================== 頂部全域導航與即時報價控制列 ==================== -->
  <header class="sticky top-0 z-40 bg-[#0a0d12]/95 backdrop-blur-md border-b border-[#262d3d]">
    <div class="max-w-[1720px] mx-auto px-3 sm:px-5 py-2 flex flex-wrap items-center justify-between gap-2">
      <!-- 左側：終端品牌與階層式麵包屑導覽 -->
      <div class="flex items-center flex-wrap gap-2 sm:gap-3">
        <button onclick="navigateTo('market')" class="flex items-center gap-2 text-left group">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 via-amber-500 to-emerald-500 p-[1.5px] shrink-0">
            <div class="w-full h-full bg-[#121722] rounded-[6px] flex items-center justify-center">
              <svg class="w-4 h-4 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                <path d="M3 3v18h18" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M7 16l4-5 3 3 6-8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
          <div>
            <div class="flex items-center gap-1.5">
              <span class="font-bold text-sm sm:text-base text-white tracking-tight group-hover:text-red-400 transition">台灣指數・機構看盤終端</span>
              <span class="hidden md:inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-red-500/15 text-red-400 border border-red-500/30">
                <span class="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
                TAIEX LIVE
              </span>
            </div>
          </div>
        </button>

        <!-- 階層式麵包屑 (Breadcrumb) -->
        <nav aria-label="Breadcrumb" class="flex items-center flex-wrap gap-1 text-xs sm:text-sm border-l border-[#262d3d] pl-2 sm:pl-3">
          <button id="crumbMarket" onclick="navigateTo('market')" class="flex items-center gap-1 px-2.5 py-1 rounded-lg font-semibold transition bg-red-500/20 text-red-300 border border-red-500/40">
            <span>台灣加權指數總覽</span>
          </button>
          <span class="text-[#848e9c]">›</span>
          <button id="crumbScreener" onclick="navigateTo('screener')" class="flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition text-[#848e9c] hover:text-white hover:bg-[#192030]">
            <span>中小型股雷達</span>
          </button>
          <span class="text-[#848e9c]">›</span>
          <button id="crumbStock" onclick="navigateTo('stock')" class="flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition text-[#848e9c] hover:text-white hover:bg-[#192030]">
            <span id="crumbStockLabel">3324 雙鴻</span>
          </button>
        </nav>
      </div>

      <!-- 右側：快速搜尋框 + 即時報價模擬開關 (1x / 3x) -->
      <div class="flex items-center gap-2 ml-auto">
        <!-- 即時搜尋框 -->
        <div class="relative w-48 sm:w-64 md:w-72">
          <div class="relative flex items-center">
            <svg class="w-3.5 h-3.5 text-[#848e9c] absolute left-2.5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            <input id="globalSearchInput" type="text" autocomplete="off" placeholder="搜尋代號/股名 (如 2330, 雙鴻)..."
              class="w-full bg-[#121722] border border-[#262d3d] focus:border-red-500 rounded-lg pl-8 pr-7 py-1.5 text-xs text-white placeholder-[#848e9c] outline-none transition" />
            <button id="clearSearchBtn" onclick="clearSearch()" class="hidden absolute right-2 text-[#848e9c] hover:text-white text-xs">✕</button>
          </div>
          <div id="searchDropdown" class="hidden absolute right-0 mt-1.5 w-72 sm:w-80 bg-[#121722] border border-[#262d3d] rounded-xl shadow-2xl overflow-hidden z-50 max-h-80 overflow-y-auto"></div>
        </div>

        <!-- 即時報價模擬開關與速度 -->
        <div class="flex items-center bg-[#121722] border border-[#262d3d] rounded-lg p-0.5 shrink-0">
          <button id="simToggleBtn" onclick="toggleSimulation()" class="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            <span id="simStatusDot" class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span id="simStatusLabel" class="hidden sm:inline">即時模擬: 開</span>
            <span class="sm:hidden">ON</span>
          </button>
          <button id="simSpeed1x" onclick="setSimSpeed(1)" class="px-2 py-1 text-[11px] font-mono rounded-md bg-blue-600 text-white ml-1 transition">1x</button>
          <button id="simSpeed3x" onclick="setSimSpeed(3)" class="px-2 py-1 text-[11px] font-mono rounded-md text-[#848e9c] hover:text-white transition">3x</button>
        </div>
      </div>
    </div>
  </header>

  <!-- 非阻斷式提示橫幅容器 -->
  <div id="toastContainer" class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none max-w-sm"></div>

  <!-- ==================== 主內容視圖容器 ==================== -->
  <main class="flex-1 max-w-[1720px] w-full mx-auto px-3 sm:px-5 py-4 space-y-5">

    <!-- =========================================================================
         VIEW 1: 主畫面 — 以「台灣加權指數 (TAIEX)」為首屏核心優先顯示
         ========================================================================= -->
    <section id="viewMarket" class="space-y-5">

      <!-- 1. 首屏核心焦點區 (Hero Section)：左側大型台灣指數即時圖表 + 右側大盤籌碼/廣度/權值貢獻/櫃買快捷卡 -->
      <div class="grid grid-cols-1 xl:grid-cols-12 gap-4">

        <!-- 左側 8 欄：台灣加權指數 (TAIEX) 超大字體核心報價與全功能互動式圖表 -->
        <div class="xl:col-span-8 bg-[#121722] border border-[#262d3d] rounded-xl p-4 sm:p-5 flex flex-col justify-between shadow-xl">
          <!-- 頂部超大字體台灣加權指數報價區 -->
          <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3.5 border-b border-[#262d3d]">
            <div>
              <div class="flex flex-wrap items-center gap-2">
                <span class="px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-bold tracking-wider">首屏核心指標</span>
                <h1 id="heroIndexTitle" class="text-xl sm:text-2xl font-black text-white tracking-tight">台灣加權指數 <span class="font-mono text-sm font-semibold text-[#848e9c]">TAIEX</span></h1>
                <button id="heroSwitchToTaiexBtn" onclick="switchHeroIndex('TAIEX')" class="hidden px-2.5 py-0.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition">
                  切回加權指數
                </button>
              </div>

              <!-- 超大即時點數與漲跌 -->
              <div id="heroIndexPriceBox" class="flex flex-wrap items-baseline gap-3 mt-1.5 px-1.5 py-0.5 rounded-lg tabular-nums">
                <span id="heroIndexPrice" class="text-4xl sm:text-5xl font-black text-red-400 tracking-tight">23,186.42</span>
                <div class="flex items-baseline gap-2 text-base sm:text-lg font-bold text-red-400">
                  <span id="heroIndexChange">▲ +224.19</span>
                  <span id="heroIndexChangePct" class="px-2 py-0.5 rounded-md bg-red-500/15 border border-red-500/30 text-sm sm:text-base">+0.98%</span>
                </div>
              </div>
            </div>

            <!-- 右側大盤開高低收與預估總成交金額 -->
            <div class="grid grid-cols-3 sm:grid-cols-5 gap-2.5 sm:gap-4 bg-[#0a0d12]/90 border border-[#262d3d] rounded-xl p-3 text-xs tabular-nums">
              <div>
                <span class="text-[#848e9c] block text-[11px]">開盤指數</span>
                <span id="heroIndexOpen" class="font-bold text-sm text-red-400">23,012.50</span>
              </div>
              <div>
                <span class="text-[#848e9c] block text-[11px]">最高指數</span>
                <span id="heroIndexHigh" class="font-bold text-sm text-red-400">23,218.90</span>
              </div>
              <div>
                <span class="text-[#848e9c] block text-[11px]">最低指數</span>
                <span id="heroIndexLow" class="font-bold text-sm text-emerald-400">22,995.10</span>
              </div>
              <div>
                <span class="text-[#848e9c] block text-[11px]">昨日收盤</span>
                <span id="heroIndexPrev" class="font-bold text-sm text-slate-200">22,962.23</span>
              </div>
              <div class="col-span-2 sm:col-span-1">
                <span class="text-[#848e9c] block text-[11px]">預估總成交額</span>
                <span id="heroIndexTurnover" class="font-bold text-sm text-amber-400">4,268.5 億</span>
              </div>
            </div>
          </div>

          <!-- 大盤圖表控制列：週期切換 + 主圖均線/布林疊加 + 縮放 -->
          <div class="flex flex-wrap items-center justify-between gap-2 py-2.5 border-b border-[#262d3d]">
            <!-- 週期切換按鈕 -->
            <div class="flex items-center flex-wrap gap-1 bg-[#0a0d12] p-1 rounded-lg border border-[#262d3d]">
              <button onclick="setHeroTimeframe('intraday')" id="htf_intraday" class="htf-btn px-2.5 py-1 text-xs rounded-md font-semibold bg-red-600 text-white transition">即時分時走勢</button>
              <button onclick="setHeroTimeframe('1m')" id="htf_1m" class="htf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">1分K</button>
              <button onclick="setHeroTimeframe('5m')" id="htf_5m" class="htf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">5分K</button>
              <button onclick="setHeroTimeframe('15m')" id="htf_15m" class="htf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">15分K</button>
              <button onclick="setHeroTimeframe('1d')" id="htf_1d" class="htf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">日K</button>
              <button onclick="setHeroTimeframe('1w')" id="htf_1w" class="htf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">週K</button>
            </div>

            <!-- 主圖技術疊加開關 + 縮放控制 -->
            <div class="flex items-center flex-wrap gap-1.5 text-[11px]">
              <button onclick="toggleHeroOverlay('MA5')" id="hov_MA5" class="px-2 py-1 rounded border font-mono transition bg-amber-500/20 text-amber-300 border-amber-500/40">MA5</button>
              <button onclick="toggleHeroOverlay('MA10')" id="hov_MA10" class="px-2 py-1 rounded border font-mono transition bg-purple-500/20 text-purple-300 border-purple-500/40">MA10</button>
              <button onclick="toggleHeroOverlay('MA20')" id="hov_MA20" class="px-2 py-1 rounded border font-mono transition bg-cyan-500/20 text-cyan-300 border-cyan-500/40">MA20</button>
              <button onclick="toggleHeroOverlay('MA60')" id="hov_MA60" class="px-2 py-1 rounded border font-mono transition bg-[#0a0d12] text-[#848e9c] border-[#262d3d]">MA60</button>
              <button onclick="toggleHeroOverlay('BOLL')" id="hov_BOLL" class="px-2 py-1 rounded border font-medium transition bg-[#0a0d12] text-[#848e9c] border-[#262d3d]">布林通道</button>

              <div class="flex items-center bg-[#0a0d12] rounded border border-[#262d3d] ml-1">
                <button onclick="zoomHeroChart(0.8)" title="放大" class="px-2 py-1 text-slate-300 hover:text-white font-bold">+</button>
                <button onclick="zoomHeroChart(1.25)" title="縮小" class="px-2 py-1 text-slate-300 hover:text-white font-bold border-x border-[#262d3d]">−</button>
                <button onclick="resetHeroZoom()" title="重置" class="px-2 py-1 text-[#848e9c] hover:text-white">重置</button>
              </div>
            </div>
          </div>

          <!-- 固定高度十字線即時讀數條 -->
          <div id="heroChartReadoutBar" class="min-h-[28px] py-1 px-2.5 my-1.5 bg-[#0a0d12] rounded-lg border border-[#262d3d]/80 flex flex-wrap items-center justify-between gap-2 text-[11px] tabular-nums">
            <!-- 由 JS 動態填充 -->
          </div>

          <!-- 大型台灣指數互動式 HTML5 Canvas 畫布 -->
          <div class="relative w-full h-[340px] sm:h-[410px] select-none">
            <canvas id="heroIndexCanvas" class="w-full h-full rounded-lg interactive-chart"></canvas>
          </div>

          <!-- 底部副圖指標切換列 (成交金額柱狀圖 / MACD / KD) -->
          <div class="flex flex-wrap items-center justify-between gap-2 pt-2.5 mt-2 border-t border-[#262d3d] text-xs">
            <div class="flex items-center gap-1.5">
              <span class="text-[#848e9c] text-[11px]">大盤副圖指標：</span>
              <button onclick="setHeroSubIndicator('VOL')" id="hsub_VOL" class="px-2.5 py-1 rounded-md font-medium bg-blue-600 text-white transition">成交金額 (億)</button>
              <button onclick="setHeroSubIndicator('MACD')" id="hsub_MACD" class="px-2.5 py-1 rounded-md font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">MACD (12,26,9)</button>
              <button onclick="setHeroSubIndicator('KD')" id="hsub_KD" class="px-2.5 py-1 rounded-md font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">KD (9,3,3)</button>
            </div>
            <span class="text-[11px] text-[#848e9c]">支援滑鼠十字線精確查價・滾輪縮放與按住拖曳平移</span>
          </div>
        </div>

        <!-- 右側 4 欄：台灣指數即時籌碼、市場廣度、權值股貢獻排行與櫃買指數快捷卡 -->
        <div class="xl:col-span-4 flex flex-col justify-between gap-3.5">

          <!-- 卡片 A：大盤漲跌家數市場廣度 (含漲停/跌停視覺比例條) -->
          <div class="bg-[#121722] border border-[#262d3d] rounded-xl p-3.5 shadow-lg">
            <div class="flex items-center justify-between mb-2">
              <h2 class="text-sm font-bold text-white flex items-center gap-1.5">
                <span class="w-1.5 h-4 rounded-sm bg-red-500"></span>
                大盤市場廣度 (漲跌家數結構)
              </h2>
              <span class="text-[11px] font-mono text-[#848e9c]">上市全體 1,012 家</span>
            </div>

            <!-- 漲 / 平 / 跌 三色比例橫條 -->
            <div class="w-full h-3 rounded-full bg-[#0a0d12] overflow-hidden flex my-2 border border-[#262d3d]">
              <div id="breadthUpBar" class="bg-red-500 h-full transition-all duration-500" style="width: 66%"></div>
              <div id="breadthFlatBar" class="bg-slate-500 h-full transition-all duration-500" style="width: 6%"></div>
              <div id="breadthDownBar" class="bg-emerald-500 h-full transition-all duration-500" style="width: 28%"></div>
            </div>

            <div class="grid grid-cols-3 gap-2 text-center text-xs tabular-nums mt-2">
              <div class="bg-[#0a0d12] rounded-lg p-2 border border-red-500/20">
                <span class="text-[#848e9c] text-[11px] block">上漲 (漲停)</span>
                <span class="text-red-400 font-bold text-sm"><span id="breadthUpCount">668</span> <span class="text-xs px-1 rounded bg-red-500/20">▲<span id="limitUpNum">26</span></span></span>
              </div>
              <div class="bg-[#0a0d12] rounded-lg p-2 border border-[#262d3d]">
                <span class="text-[#848e9c] text-[11px] block">平盤家數</span>
                <span id="breadthFlatCount" class="text-slate-300 font-bold text-sm">61</span>
              </div>
              <div class="bg-[#0a0d12] rounded-lg p-2 border border-emerald-500/20">
                <span class="text-[#848e9c] text-[11px] block">下跌 (跌停)</span>
                <span class="text-emerald-400 font-bold text-sm"><span id="breadthDownCount">283</span> <span class="text-xs px-1 rounded bg-emerald-500/20">▼<span id="limitDownNum">2</span></span></span>
              </div>
            </div>
          </div>

          <!-- 卡片 B：三大法人現貨買賣超 & 外資台指期未平倉 -->
          <div class="bg-[#121722] border border-[#262d3d] rounded-xl p-3.5 shadow-lg">
            <div class="flex items-center justify-between mb-2">
              <h2 class="text-sm font-bold text-white flex items-center gap-1.5">
                <span class="w-1.5 h-4 rounded-sm bg-blue-500"></span>
                三大法人現貨 & 期貨籌碼動向
              </h2>
              <span class="text-[11px] font-semibold text-red-400">現貨合計 +184.6 億</span>
            </div>

            <div class="grid grid-cols-4 gap-1.5 text-xs tabular-nums">
              <div class="bg-[#0a0d12] rounded-lg p-2 border border-[#262d3d]">
                <span class="text-[#848e9c] text-[10px] block">外資現貨</span>
                <span class="text-red-400 font-bold text-xs sm:text-sm">+152.4億</span>
              </div>
              <div class="bg-[#0a0d12] rounded-lg p-2 border border-[#262d3d]">
                <span class="text-[#848e9c] text-[10px] block">投信現貨</span>
                <span class="text-red-400 font-bold text-xs sm:text-sm">+38.9億</span>
              </div>
              <div class="bg-[#0a0d12] rounded-lg p-2 border border-[#262d3d]">
                <span class="text-[#848e9c] text-[10px] block">自營商</span>
                <span class="text-emerald-400 font-bold text-xs sm:text-sm">-6.7億</span>
              </div>
              <div class="bg-[#0a0d12] rounded-lg p-2 border border-amber-500/30">
                <span class="text-amber-400 text-[10px] block">外資期貨淨口</span>
                <span class="text-emerald-400 font-bold text-xs sm:text-sm">-30,420</span>
              </div>
            </div>
          </div>

          <!-- 卡片 C：權值股貢獻排行 (點擊可直接下鑽該個股) -->
          <div class="bg-[#121722] border border-[#262d3d] rounded-xl p-3.5 shadow-lg">
            <div class="flex items-center justify-between mb-2">
              <h2 class="text-sm font-bold text-white flex items-center gap-1.5">
                <span class="w-1.5 h-4 rounded-sm bg-amber-400"></span>
                大盤權值股貢獻點數排行
              </h2>
              <span class="text-[10px] text-[#848e9c]">點擊個股直接下鑽 K 線</span>
            </div>
            <div id="heavyweightList" class="space-y-1.5 text-xs tabular-nums">
              <!-- 由 JS 渲染台積電、鴻海、聯發科、廣達、富邦金 -->
            </div>
          </div>

          <!-- 卡片 D：櫃買指數 (OTC 中小型股指標) 快捷切換與下鑽卡 -->
          <div class="bg-gradient-to-r from-[#121722] to-[#192234] border border-amber-500/40 rounded-xl p-3.5 shadow-lg">
            <div class="flex items-center justify-between">
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="text-sm font-bold text-white">櫃買指數</span>
                  <span class="font-mono text-xs text-[#848e9c]">OTC</span>
                  <span class="px-1.5 py-0.2 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30">中小型股風向球</span>
                </div>
                <div class="flex items-baseline gap-2 mt-1 tabular-nums">
                  <span id="otcCardPrice" class="text-2xl font-black text-red-400">270.48</span>
                  <span id="otcCardChange" class="text-xs font-bold text-red-400">▲ +4.06 (+1.52%)</span>
                </div>
              </div>
              <div class="flex flex-col gap-1.5 shrink-0">
                <button onclick="switchHeroIndex('OTC')" class="px-3 py-1.5 rounded-lg bg-[#0a0d12] hover:bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-semibold transition">
                  主圖切看櫃買
                </button>
                <button onclick="navigateTo('screener')" class="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition shadow">
                  下鑽中小型股 ↓
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- 2. 主畫面下半部第一區：熱門產業族群資金熱力圖 (Sector Heatmap) -->
      <div class="bg-[#121722] border border-[#262d3d] rounded-xl p-4 shadow-lg">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div class="flex items-center gap-2">
            <h2 class="text-base font-bold text-white flex items-center gap-2">
              <span class="w-2 h-5 rounded-sm bg-red-500 inline-block"></span>
              熱門產業族群資金熱力圖 (點擊族群過濾下方中小型股)
            </h2>
          </div>
          <div class="flex items-center gap-2">
            <span id="activeSectorBadge" class="hidden px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40"></span>
            <button onclick="selectSectorFilter('ALL')" class="px-3 py-1 rounded-lg text-xs font-medium bg-[#192030] hover:bg-blue-600 text-slate-200 hover:text-white border border-[#262d3d] transition">
              顯示全部族群
            </button>
          </div>
        </div>

        <div id="sectorHeatmapGrid" class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
          <!-- 由 JS 渲染 8 大產業族群 -->
        </div>
      </div>

      <!-- 3. 主畫面下半部第二區：中小型潛力股即時看板 (Small & Mid-Cap Screener) -->
      <div id="screenerSection" class="bg-[#121722] border border-[#262d3d] rounded-xl p-4 shadow-lg scroll-mt-20">
        <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3.5 border-b border-[#262d3d]">
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-base sm:text-lg font-bold text-white">中小型潛力股即時雷達 (Small & Mid-Cap Screener)</h2>
              <span id="screenerCountBadge" class="px-2.5 py-0.5 text-xs font-mono rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">16 檔標的</span>
            </div>
            <p class="text-xs text-[#848e9c] mt-0.5">點擊任一股票列，立即下鑽進入第二層「個股即時 K 線・五檔明細・五大深度分析終端」</p>
          </div>

          <!-- 快速篩選按鈕組 -->
          <div class="flex flex-wrap items-center gap-1.5 text-xs">
            <button onclick="setQuickFilter('ALL')" id="qf_ALL" class="qf-btn px-3 py-1.5 rounded-lg font-semibold bg-blue-600 text-white transition">全部標的</button>
            <button onclick="setQuickFilter('CAP20')" id="qf_CAP20" class="qf-btn px-3 py-1.5 rounded-lg font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">股本 &lt; 20億</button>
            <button onclick="setQuickFilter('CAP50')" id="qf_CAP50" class="qf-btn px-3 py-1.5 rounded-lg font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">股本 &lt; 50億</button>
            <button onclick="setQuickFilter('VOL_SURGE')" id="qf_VOL_SURGE" class="qf-btn px-3 py-1.5 rounded-lg font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">爆量突破 (量比&gt;1.5)</button>
            <button onclick="setQuickFilter('INST_STREAK')" id="qf_INST_STREAK" class="qf-btn px-3 py-1.5 rounded-lg font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">法人連買 (≥3日)</button>
          </div>
        </div>

        <!-- 響應式可排序個股雷達表格 -->
        <div class="overflow-x-auto mt-3">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="border-b border-[#262d3d] text-[11px] font-semibold text-[#848e9c] uppercase tracking-wider select-none">
                <th class="py-2.5 px-3 cursor-pointer hover:text-white" onclick="sortScreener('code')">代號 / 股名 <span id="sort_code"></span></th>
                <th class="py-2.5 px-2.5 cursor-pointer hover:text-white" onclick="sortScreener('sector')">產業族群 <span id="sort_sector"></span></th>
                <th class="py-2.5 px-2.5 text-right cursor-pointer hover:text-white" onclick="sortScreener('capital')">股本(億) <span id="sort_capital"></span></th>
                <th class="py-2.5 px-3 text-right cursor-pointer hover:text-white" onclick="sortScreener('price')">即時價 <span id="sort_price"></span></th>
                <th class="py-2.5 px-3 text-right cursor-pointer hover:text-white" onclick="sortScreener('changePct')">漲跌幅(%) <span id="sort_changePct">▼</span></th>
                <th class="py-2.5 px-3 text-right cursor-pointer hover:text-white" onclick="sortScreener('volume')">成交量(張) <span id="sort_volume"></span></th>
                <th class="py-2.5 px-2.5 text-right cursor-pointer hover:text-white" onclick="sortScreener('volRatio')">量比 <span id="sort_volRatio"></span></th>
                <th class="py-2.5 px-3 text-right cursor-pointer hover:text-white" onclick="sortScreener('instStreak')">法人連買天數 <span id="sort_instStreak"></span></th>
                <th class="py-2.5 px-3 text-center">當日迷你走勢</th>
                <th class="py-2.5 px-3 text-right">下鑽分析</th>
              </tr>
            </thead>
            <tbody id="screenerTableBody" class="divide-y divide-[#262d3d]/60 text-xs sm:text-sm tabular-nums">
              <!-- 由 JS 動態生成 16 檔中小型股 -->
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- =========================================================================
         VIEW 2: 個股即時 K 線與五大深度功能終端 (Stock Deep-Dive Terminal)
         ========================================================================= -->
    <section id="viewStock" class="hidden space-y-4">

      <!-- 1. 個股頂部即時報價與快速切換列 -->
      <div class="bg-[#121722] border border-[#262d3d] rounded-xl p-3.5 sm:p-4 shadow-lg">
        <div class="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
          <div class="flex flex-wrap items-center gap-3">
            <button onclick="navigateTo('market')" class="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#192030] hover:bg-red-600 text-xs sm:text-sm font-semibold text-white border border-[#262d3d] transition shrink-0">
              <span>← 返回台灣指數總覽</span>
            </button>

            <select id="stockQuickSwitcher" onchange="drillDownStock(this.value)" class="bg-[#0a0d12] border border-[#262d3d] focus:border-blue-500 rounded-lg px-3 py-2 text-xs sm:text-sm font-medium text-white outline-none cursor-pointer">
              <!-- 由 JS 填充所有標的 (含權值股與中小型股) -->
            </select>

            <div>
              <div class="flex flex-wrap items-center gap-2">
                <h1 id="detailStockTitle" class="text-xl sm:text-2xl font-bold text-white tracking-tight">3324 雙鴻</h1>
                <span id="detailMarketBadge" class="px-2 py-0.5 text-xs font-semibold rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">上櫃 OTC</span>
                <span id="detailCapitalBadge" class="px-2 py-0.5 text-xs font-mono rounded bg-slate-700/60 text-slate-200 border border-slate-600">股本 9.1 億</span>
                <span id="detailSectorBadge" class="px-2 py-0.5 text-xs font-medium rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">AI散熱模組</span>
              </div>
              <p id="detailCompanyDesc" class="text-xs text-[#848e9c] mt-0.5"></p>
            </div>
          </div>

          <!-- 右側即時報價與六大關鍵數據 -->
          <div class="flex flex-wrap items-center justify-between xl:justify-end gap-4 sm:gap-6 pt-3 xl:pt-0 border-t xl:border-t-0 border-[#262d3d] tabular-nums">
            <div id="detailPriceBox" class="px-2 py-1 rounded-lg">
              <div class="flex items-baseline gap-2.5">
                <span id="detailPrice" class="text-3xl sm:text-4xl font-bold text-red-400">742.0</span>
                <div class="flex flex-col text-xs sm:text-sm font-bold text-red-400">
                  <span id="detailChange">▲ +34.0</span>
                  <span id="detailChangePct">+4.80%</span>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-3 sm:grid-cols-6 gap-x-4 gap-y-1.5 text-xs">
              <div><span class="text-[#848e9c] block text-[11px]">開盤</span><span id="detailOpen" class="font-semibold text-red-400">715.0</span></div>
              <div><span class="text-[#848e9c] block text-[11px]">最高</span><span id="detailHigh" class="font-semibold text-red-400">748.0</span></div>
              <div><span class="text-[#848e9c] block text-[11px]">最低</span><span id="detailLow" class="font-semibold text-emerald-400">712.0</span></div>
              <div><span class="text-[#848e9c] block text-[11px]">昨收</span><span id="detailPrevClose" class="font-semibold text-slate-200">708.0</span></div>
              <div><span class="text-[#848e9c] block text-[11px]">振幅</span><span id="detailAmplitude" class="font-semibold text-amber-400">5.08%</span></div>
              <div><span class="text-[#848e9c] block text-[11px]">成交金額</span><span id="detailTurnoverAmt" class="font-semibold text-white">68.42 億</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. 核心工作區：左側互動式 K 線圖表 (8/9欄) + 右側最佳五檔與分時明細 (4/3欄) -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div class="lg:col-span-8 xl:col-span-9 bg-[#121722] border border-[#262d3d] rounded-xl p-3 sm:p-4 flex flex-col justify-between shadow-lg">
          <!-- 工具列：週期 + 疊加指標 + 縮放 -->
          <div class="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-[#262d3d]">
            <div class="flex items-center flex-wrap gap-1 bg-[#0a0d12] p-1 rounded-lg border border-[#262d3d]">
              <button onclick="setChartTimeframe('intraday')" id="tf_intraday" class="tf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">分時</button>
              <button onclick="setChartTimeframe('1m')" id="tf_1m" class="tf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">1分K</button>
              <button onclick="setChartTimeframe('5m')" id="tf_5m" class="tf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">5分K</button>
              <button onclick="setChartTimeframe('15m')" id="tf_15m" class="tf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">15分K</button>
              <button onclick="setChartTimeframe('60m')" id="tf_60m" class="tf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">60分K</button>
              <button onclick="setChartTimeframe('1d')" id="tf_1d" class="tf-btn px-2.5 py-1 text-xs rounded-md font-medium bg-blue-600 text-white transition">日K</button>
              <button onclick="setChartTimeframe('1w')" id="tf_1w" class="tf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition">週K</button>
            </div>

            <div class="flex items-center flex-wrap gap-1.5 text-[11px]">
              <button onclick="toggleOverlay('MA5')" id="ov_MA5" class="px-2 py-1 rounded border font-mono transition bg-amber-500/20 text-amber-300 border-amber-500/40">MA5</button>
              <button onclick="toggleOverlay('MA10')" id="ov_MA10" class="px-2 py-1 rounded border font-mono transition bg-purple-500/20 text-purple-300 border-purple-500/40">MA10</button>
              <button onclick="toggleOverlay('MA20')" id="ov_MA20" class="px-2 py-1 rounded border font-mono transition bg-cyan-500/20 text-cyan-300 border-cyan-500/40">MA20</button>
              <button onclick="toggleOverlay('MA60')" id="ov_MA60" class="px-2 py-1 rounded border font-mono transition bg-[#0a0d12] text-[#848e9c] border-[#262d3d]">MA60</button>
              <button onclick="toggleOverlay('BOLL')" id="ov_BOLL" class="px-2 py-1 rounded border font-medium transition bg-[#0a0d12] text-[#848e9c] border-[#262d3d]">布林通道</button>
              <button onclick="toggleOverlay('VWAP')" id="ov_VWAP" class="px-2 py-1 rounded border font-mono transition bg-[#0a0d12] text-[#848e9c] border-[#262d3d]">VWAP</button>

              <div class="flex items-center bg-[#0a0d12] rounded border border-[#262d3d] ml-1">
                <button onclick="zoomChart(0.8)" title="放大" class="px-2 py-1 text-slate-300 hover:text-white font-bold">+</button>
                <button onclick="zoomChart(1.25)" title="縮小" class="px-2 py-1 text-slate-300 hover:text-white font-bold border-x border-[#262d3d]">−</button>
                <button onclick="resetChartZoom()" title="重置" class="px-2 py-1 text-[#848e9c] hover:text-white">重置</button>
              </div>
            </div>
          </div>

          <!-- 固定高度 OHLCV 十字線即時讀數條 -->
          <div id="klineReadoutBar" class="min-h-[28px] py-1 px-2 my-1 bg-[#0a0d12]/90 rounded-lg border border-[#262d3d]/70 flex flex-wrap items-center justify-between gap-2 text-[11px] tabular-nums"></div>

          <!-- 個股主圖畫布 -->
          <div class="relative w-full h-[360px] sm:h-[430px] select-none">
            <canvas id="stockMainCanvas" class="w-full h-full rounded-lg interactive-chart"></canvas>
          </div>

          <!-- 副圖切換列 -->
          <div class="flex flex-wrap items-center justify-between gap-2 pt-2.5 mt-2 border-t border-[#262d3d] text-xs">
            <div class="flex items-center gap-1.5">
              <span class="text-[#848e9c] text-[11px]">副圖指標：</span>
              <button onclick="setSubIndicator('VOL')" id="sub_VOL" class="px-2.5 py-1 rounded-md font-medium bg-blue-600 text-white transition">成交量 (VOL)</button>
              <button onclick="setSubIndicator('MACD')" id="sub_MACD" class="px-2.5 py-1 rounded-md font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">MACD (12,26,9)</button>
              <button onclick="setSubIndicator('KD')" id="sub_KD" class="px-2.5 py-1 rounded-md font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">KD (9,3,3)</button>
              <button onclick="setSubIndicator('RSI')" id="sub_RSI" class="px-2.5 py-1 rounded-md font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition">RSI (6 / 12)</button>
            </div>
            <span class="text-[11px] text-[#848e9c] hidden sm:inline">支援滾輪縮放・按住拖曳平移歷史區間</span>
          </div>
        </div>

        <!-- 右側盤口即時模組：最佳五檔 + 內外盤比例 + 即時成交明細 -->
        <div class="lg:col-span-4 xl:col-span-3 bg-[#121722] border border-[#262d3d] rounded-xl p-3.5 flex flex-col justify-between shadow-lg">
          <div>
            <div class="flex items-center justify-between pb-2 border-b border-[#262d3d]">
              <h3 class="text-sm font-bold text-white">最佳五檔報價 (Order Book)</h3>
              <span id="orderBookSpread" class="text-[11px] font-mono text-[#848e9c]">檔位: 1.0</span>
            </div>

            <!-- 內外盤比例條 -->
            <div class="my-2.5">
              <div class="flex justify-between text-[11px] tabular-nums mb-1">
                <span class="text-red-400 font-semibold">外盤 <span id="outerRatioText">58.4%</span></span>
                <span class="text-emerald-400 font-semibold"><span id="innerRatioText">41.6%</span> 內盤</span>
              </div>
              <div class="w-full h-2 rounded-full bg-emerald-500/30 overflow-hidden flex">
                <div id="outerRatioBar" class="bg-red-500 h-full transition-all duration-300" style="width: 58.4%"></div>
                <div id="innerRatioBar" class="bg-emerald-500 h-full transition-all duration-300" style="width: 41.6%"></div>
              </div>
            </div>

            <div class="space-y-1 text-xs tabular-nums" id="askLevelsContainer"></div>

            <div class="my-2 py-1.5 px-2.5 rounded-lg bg-[#0a0d12] border border-[#262d3d] flex items-center justify-between text-xs tabular-nums">
              <span class="text-[#848e9c]">最新成交</span>
              <span id="bookLastPrice" class="font-bold text-base text-red-400">742.0</span>
              <span id="bookLastVol" class="text-amber-400 font-mono">單量 18 張</span>
            </div>

            <div class="space-y-1 text-xs tabular-nums" id="bidLevelsContainer"></div>
          </div>

          <div class="mt-3 pt-2.5 border-t border-[#262d3d]">
            <div class="flex items-center justify-between mb-1.5">
              <h4 class="text-xs font-bold text-white">即時分時成交明細 (Tick Tape)</h4>
              <span class="text-[10px] text-[#848e9c]">時間 / 成交 / 單量</span>
            </div>
            <div id="tickTapeContainer" class="h-44 overflow-y-auto space-y-1 pr-1 text-xs tabular-nums"></div>
          </div>
        </div>
      </div>

      <!-- 3. 底部五大細分功能分頁籤 (Sub-feature Tabs) -->
      <div class="bg-[#121722] border border-[#262d3d] rounded-xl shadow-lg overflow-hidden">
        <div class="flex items-center overflow-x-auto border-b border-[#262d3d] bg-[#0a0d12]/70 px-2 pt-2 gap-1">
          <button onclick="setDetailTab('tech')" id="tabBtn_tech" class="detail-tab-btn px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-lg border-t border-x border-[#262d3d] bg-[#121722] text-blue-400 whitespace-nowrap transition">
            1. 技術面分析
          </button>
          <button onclick="setDetailTab('chips')" id="tabBtn_chips" class="detail-tab-btn px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-lg border-t border-x border-transparent text-[#848e9c] hover:text-white whitespace-nowrap transition">
            2. 籌碼面追蹤
          </button>
          <button onclick="setDetailTab('fund')" id="tabBtn_fund" class="detail-tab-btn px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-lg border-t border-x border-transparent text-[#848e9c] hover:text-white whitespace-nowrap transition">
            3. 基本面與估值
          </button>
          <button onclick="setDetailTab('peers')" id="tabBtn_peers" class="detail-tab-btn px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-lg border-t border-x border-transparent text-[#848e9c] hover:text-white whitespace-nowrap transition">
            4. 同業族群對比
          </button>
          <button onclick="setDetailTab('alerts')" id="tabBtn_alerts" class="detail-tab-btn px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-lg border-t border-x border-transparent text-[#848e9c] hover:text-white whitespace-nowrap transition">
            5. 觸價預警與筆記
          </button>
        </div>

        <div class="p-4 sm:p-5">
          <!-- TAB 1: 技術面分析 -->
          <div id="tabPanel_tech" class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4">
              <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-bold text-white">多週期均線與趨勢共振</h4>
                <span id="resonanceBadge" class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-500/20 text-red-400 border border-red-500/30">偏多主導</span>
              </div>
              <div id="mtfMatrixGrid" class="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs"></div>
            </div>

            <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4">
              <h4 class="text-sm font-bold text-white mb-3">KD / MACD / RSI 訊號儀表板</h4>
              <div id="techDiagnosisList" class="space-y-2.5 text-xs"></div>
            </div>

            <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4">
              <h4 class="text-sm font-bold text-white mb-3">關鍵支撐與壓力位計算 (Pivot)</h4>
              <div id="pivotLevelsList" class="space-y-2 text-xs tabular-nums"></div>
            </div>
          </div>

          <!-- TAB 2: 籌碼面追蹤 -->
          <div id="tabPanel_chips" class="hidden space-y-4">
            <div id="chipSummaryCards" class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs tabular-nums"></div>
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-4">
              <div class="lg:col-span-7 bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4">
                <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <h4 class="text-sm font-bold text-white">近 15 日三大法人買賣超長條圖 (張)</h4>
                  <div class="flex items-center gap-3 text-[11px]">
                    <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-blue-500 inline-block"></span>外資</span>
                    <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-red-500 inline-block"></span>投信</span>
                    <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block"></span>自營商</span>
                  </div>
                </div>
                <div id="instChartTooltip" class="h-5 text-[11px] text-[#848e9c] tabular-nums mb-1">移動滑鼠檢視每日法人買賣超明細</div>
                <div class="w-full h-56"><canvas id="instChipsCanvas" class="w-full h-full interactive-chart"></canvas></div>
              </div>

              <div class="lg:col-span-5 bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4 flex flex-col justify-between space-y-3">
                <div>
                  <h4 class="text-sm font-bold text-white mb-2.5">主力前五大買賣超分點明細表</h4>
                  <div class="grid grid-cols-2 gap-2.5 text-[11px] tabular-nums">
                    <div>
                      <div class="text-red-400 font-semibold pb-1 border-b border-[#262d3d] mb-1.5">▲ 買超分點 (張/均價)</div>
                      <div id="topBuyBrokers" class="space-y-1.5"></div>
                    </div>
                    <div>
                      <div class="text-emerald-400 font-semibold pb-1 border-b border-[#262d3d] mb-1.5">▼ 賣超分點 (張/均價)</div>
                      <div id="topSellBrokers" class="space-y-1.5"></div>
                    </div>
                  </div>
                </div>
                <div id="marginDayTradeGauges" class="pt-3 border-t border-[#262d3d] space-y-2.5 text-xs tabular-nums"></div>
              </div>
            </div>
          </div>

          <!-- TAB 3: 基本面與估值 -->
          <div id="tabPanel_fund" class="hidden space-y-4">
            <div id="fundKpiCards" class="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs tabular-nums"></div>
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-4">
              <div class="lg:col-span-8 bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4">
                <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <h4 class="text-sm font-bold text-white">近 12 個月合併營收 (億元) 與年增率 YoY (%)</h4>
                  <div class="flex items-center gap-3 text-[11px]">
                    <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-blue-500/80 inline-block"></span>單月營收</span>
                    <span class="flex items-center gap-1"><span class="w-2.5 h-0.5 bg-amber-400 inline-block"></span>年增率 YoY (%)</span>
                  </div>
                </div>
                <div id="revChartTooltip" class="h-5 text-[11px] text-[#848e9c] tabular-nums mb-1">移動滑鼠檢視單月營收與年增率</div>
                <div class="w-full h-56"><canvas id="revenueCanvas" class="w-full h-full interactive-chart"></canvas></div>
              </div>

              <div class="lg:col-span-4 bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4 flex flex-col justify-between">
                <div>
                  <h4 class="text-sm font-bold text-white mb-1">本益比 (PE) 河流區間定位</h4>
                  <p class="text-[11px] text-[#848e9c] mb-4">依據近四季累計 EPS 與過去 3 年歷史本益比區間計算</p>
                  <div id="peBandVisual" class="space-y-4"></div>
                </div>
                <div id="fundHighlightNote" class="mt-4 p-3 rounded-lg bg-[#121722] border border-[#262d3d] text-xs text-slate-300 leading-relaxed"></div>
              </div>
            </div>
          </div>

          <!-- TAB 4: 同業族群對比 -->
          <div id="tabPanel_peers" class="hidden space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h4 id="peersSectionTitle" class="text-sm font-bold text-white">同產業族群橫向比較表</h4>
              <span class="text-xs text-[#848e9c]">點擊同業標的可直接切換過去</span>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-left border-collapse text-xs sm:text-sm tabular-nums">
                <thead>
                  <tr class="border-b border-[#262d3d] text-[11px] text-[#848e9c] uppercase">
                    <th class="py-2.5 px-3">代號 / 股名</th>
                    <th class="py-2.5 px-3 text-right">股本(億)</th>
                    <th class="py-2.5 px-3 text-right">即時價</th>
                    <th class="py-2.5 px-3 text-right">漲跌幅(%)</th>
                    <th class="py-2.5 px-3 text-right">本益比 (PE)</th>
                    <th class="py-2.5 px-3 text-right">毛利率 (%)</th>
                    <th class="py-2.5 px-3 text-right">法人連買</th>
                    <th class="py-2.5 px-3 text-right">切換</th>
                  </tr>
                </thead>
                <tbody id="peersTableBody" class="divide-y divide-[#262d3d]/60"></tbody>
              </table>
            </div>
          </div>

          <!-- TAB 5: 觸價預警與筆記 -->
          <div id="tabPanel_alerts" class="hidden grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4 space-y-3">
              <div class="flex items-center justify-between">
                <h4 class="text-sm font-bold text-white">即時觸價預警設定 (Smart Alerts)</h4>
                <span class="text-[11px] text-amber-400">開啟模擬跳動可自動觸發警示</span>
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <select id="alertConditionType" class="bg-[#121722] border border-[#262d3d] rounded-lg px-2.5 py-2 text-white outline-none">
                  <option value="PRICE_ABOVE">現價突破 (≥)</option>
                  <option value="PRICE_BELOW">現價跌破 (≤)</option>
                  <option value="PCT_ABOVE">漲幅超過 (≥ %)</option>
                </select>
                <input id="alertTargetValue" type="number" step="0.5" placeholder="輸入目標價位或%" class="bg-[#121722] border border-[#262d3d] rounded-lg px-2.5 py-2 text-white tabular-nums outline-none" />
                <button onclick="addCustomAlert()" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg px-3 py-2 transition">+ 新增警示</button>
              </div>
              <div id="activeAlertsList" class="space-y-2 max-h-48 overflow-y-auto pt-1"></div>
            </div>

            <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-4 flex flex-col justify-between space-y-3">
              <div>
                <div class="flex items-center justify-between mb-2">
                  <h4 id="tradeNoteTitle" class="text-sm font-bold text-white">個人操盤筆記</h4>
                  <span id="noteSavedStatus" class="text-[11px] text-emerald-400"></span>
                </div>
                <textarea id="tradeNoteTextarea" rows="5" placeholder="記錄進場策略、支撐壓力觀察或籌碼重點..."
                  class="w-full bg-[#121722] border border-[#262d3d] focus:border-blue-500 rounded-lg p-3 text-xs text-slate-200 placeholder-[#848e9c] outline-none resize-none leading-relaxed"></textarea>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-[11px] text-[#848e9c]">筆記依個股代號獨立儲存</span>
                <button onclick="saveTradeNote()" class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition">儲存筆記</button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>

  </main>

  <!-- ==================== 頁尾資訊 ==================== -->
  <footer class="border-t border-[#262d3d] bg-[#0a0d12] py-3 px-4 mt-6">
    <div class="max-w-[1720px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-[#848e9c]">
      <span>台灣指數優先・多維度下鑽看盤終端 | 台股紅漲綠跌視覺標準</span>
      <span>註：內建高擬真台股大盤、權值股與中小型股即時行情模擬引擎，供看盤分析架構演練使用。</span>
    </div>
  </footer>

  <!-- ==================== 核心資料庫、繪圖引擎與互動邏輯 ==================== -->
  <script>
    // =========================================================================
    // 1. 全域狀態管理
    // =========================================================================
    const state = {
      view: 'market', // 'market' | 'stock'
      heroIndexKey: 'TAIEX', // 'TAIEX' | 'OTC'
      selectedStockCode: '3324',
      simRunning: true,
      simSpeed: 1,
      heroChart: {
        timeframe: 'intraday', // 'intraday' | '1m' | '5m' | '15m' | '1d' | '1w'
        overlays: { MA5: true, MA10: true, MA20: true, MA60: false, BOLL: false },
        subIndicator: 'VOL', // 'VOL' | 'MACD' | 'KD'
        visibleBars: 65,
        offsetBars: 0,
        hoverIndex: -1,
        isDragging: false,
        dragStartX: 0,
        dragStartOffset: 0
      },
      screener: {
        sector: 'ALL',
        quickFilter: 'ALL', // 'ALL' | 'CAP20' | 'CAP50' | 'VOL_SURGE' | 'INST_STREAK'
        sortKey: 'changePct',
        sortDir: 'desc'
      },
      chart: {
        timeframe: '1d',
        overlays: { MA5: true, MA10: true, MA20: true, MA60: false, BOLL: false, VWAP: false },
        subIndicator: 'VOL',
        visibleBars: 65,
        offsetBars: 0,
        hoverIndex: -1,
        isDragging: false,
        dragStartX: 0,
        dragStartOffset: 0
      },
      detailTab: 'tech',
      alerts: [
        { id: 1, code: '3324', name: '雙鴻', type: 'PRICE_ABOVE', target: 745.0, triggered: false },
        { id: 2, code: '2330', name: '台積電', type: 'PRICE_ABOVE', target: 1090.0, triggered: false }
      ],
      notes: {
        '2330': '先進製程 CoWoS 產能持續滿載，外資買盤回籠帶動加權指數站穩兩萬三千點大關。',
        '3324': 'AI 伺服器液冷板放量出貨，投信連續買超，沿五日線偏多操作。'
      }
    };

    // 台灣加權指數 (TAIEX) 與櫃買指數 (OTC) 資料結構
    const macroIndices = {
      TAIEX: {
        name: '台灣加權指數', code: 'TAIEX',
        price: 23186.42, prevClose: 22962.23, open: 23012.50, high: 23218.90, low: 22995.10,
        turnover: 4268.5, series: {}
      },
      OTC: {
        name: '櫃買指數', code: 'OTC',
        price: 270.48, prevClose: 266.42, open: 267.15, high: 271.20, low: 266.80,
        turnover: 1084.2, series: {}
      }
    };

    // 8 大熱門產業族群熱力圖
    const sectorsData = [
      { id: 'AI散熱模組', name: 'AI散熱模組', changePct: 4.24, flow: 146.8, leader: '3324 雙鴻' },
      { id: '光通訊CPO',  name: '光通訊CPO',  changePct: 3.72, flow: 121.5, leader: '3363 上詮' },
      { id: '半導體設備', name: '半導體設備', changePct: 2.85, flow: 172.4, leader: '3680 家登' },
      { id: '矽智財IP',   name: '矽智財IP',   changePct: 2.18, flow: 99.6,  leader: '3529 力旺' },
      { id: '機器人自動化', name: '機器人自動化', changePct: 1.88, flow: 78.2,  leader: '2359 所羅門' },
      { id: '重電綠能',   name: '重電綠能',   changePct: 0.96, flow: 85.4,  leader: '1519 華城' },
      { id: 'IC設計',     name: 'IC設計',     changePct: -0.42, flow: -31.2, leader: '4966 譜瑞-KY' },
      { id: '生技新藥',   name: '生技新藥',   changePct: -1.08, flow: -23.5, leader: '6472 保瑞' }
    ];

    // 權值股清單 (顯示於大盤右側貢獻排行，並可點擊下鑽)
    const heavyweightStocksDB = [
      {
        code: '2330', name: '台積電', market: '上市', sector: '晶圓代工權值', capital: 2593.2, isHeavyweight: true,
        price: 1085.0, prevClose: 1065.0, open: 1070.0, high: 1090.0, low: 1065.0, volume: 34820, volRatio: 1.42, instStreak: 5, instNet: 12450,
        contribPts: 162.4,
        desc: '全球最大專業積體電路製造服務廠・3奈米與 CoWoS 先進封裝核心霸主',
        pe: 23.4, peRange: [15, 20, 26, 32], grossMargin: 57.8, opMargin: 47.5, roe: 30.2, divYield: 1.55, eps4Q: 46.36, revYoY: 36.8,
        foreignHold: 74.2, instHold: 5.8, marginUsage: 8.4, dayTradePct: 24.1,
        note: '先進製程與 AI 晶片代工需求強勁，外資連續買超推升加權指數走高。'
      },
      {
        code: '2317', name: '鴻海', market: '上市', sector: 'AI伺服器權值', capital: 1386.3, isHeavyweight: true,
        price: 218.5, prevClose: 214.0, open: 215.0, high: 220.0, low: 214.5, volume: 68420, volRatio: 1.35, instStreak: 4, instNet: 18620,
        contribPts: 21.8,
        desc: '全球最大電子代工服務廠・AI 伺服器機櫃與電動車平台領導廠',
        pe: 17.8, peRange: [11, 15, 19, 24], grossMargin: 6.4, opMargin: 3.1, roe: 10.8, divYield: 2.52, eps4Q: 12.28, revYoY: 22.4,
        foreignHold: 42.6, instHold: 7.4, marginUsage: 14.2, dayTradePct: 31.5,
        note: 'GB200 伺服器機櫃第四季起放量出貨，法人同步偏多佈局。'
      },
      {
        code: '2454', name: '聯發科', market: '上市', sector: 'IC設計權值', capital: 160.1, isHeavyweight: true,
        price: 1345.0, prevClose: 1325.0, open: 1330.0, high: 1355.0, low: 1325.0, volume: 6420, volRatio: 1.28, instStreak: 3, instNet: 1840,
        contribPts: 11.4,
        desc: '全球手機晶片市占龍頭・邊緣 AI 旗艦晶片天璣 9400 與雲端 ASIC 佈局',
        pe: 21.6, peRange: [14, 19, 24, 30], grossMargin: 48.8, opMargin: 21.4, roe: 26.5, divYield: 3.85, eps4Q: 62.26, revYoY: 25.1,
        foreignHold: 58.4, instHold: 8.9, marginUsage: 9.6, dayTradePct: 26.8,
        note: '旗艦手機晶片市占率持續擴大，高現金殖利率具備機構長線配置價值。'
      },
      {
        code: '2382', name: '廣達', market: '上市', sector: 'AI伺服器權值', capital: 386.3, isHeavyweight: true,
        price: 314.0, prevClose: 308.5, open: 310.0, high: 316.5, low: 308.0, volume: 28940, volRatio: 1.31, instStreak: 3, instNet: 5420,
        contribPts: 7.9,
        desc: '全球雲端伺服器 ODM 龍頭・北美四大 CSP 雲端大廠核心 AI 伺服器夥伴',
        pe: 20.4, peRange: [13, 18, 23, 29], grossMargin: 8.2, opMargin: 4.5, roe: 28.4, divYield: 2.86, eps4Q: 15.39, revYoY: 44.6,
        foreignHold: 33.8, instHold: 11.2, marginUsage: 16.8, dayTradePct: 38.4,
        note: 'AI 伺服器佔營收比重突破五成，營收年增率維持高雙位數成長。'
      },
      {
        code: '2881', name: '富邦金', market: '上市', sector: '金控權值', capital: 1366.8, isHeavyweight: true,
        price: 92.8, prevClose: 91.9, open: 92.1, high: 93.2, low: 91.8, volume: 22410, volRatio: 1.12, instStreak: 6, instNet: 8940,
        contribPts: 4.6,
        desc: '台灣金控獲利王・壽險投資收益與銀行淨利差穩健成長',
        pe: 10.8, peRange: [8, 10, 12, 15], grossMargin: 38.5, opMargin: 24.2, roe: 14.6, divYield: 3.45, eps4Q: 8.59, revYoY: 18.2,
        foreignHold: 24.1, instHold: 9.5, marginUsage: 7.2, dayTradePct: 16.4,
        note: '前十月自結 EPS 穩居金控第一，投信高股息 ETF 持續買進支撐。'
      }
    ];

    // 16 檔精選台股中小型代表標的 (Small & Mid-Cap Screener)
    const smallCapStocksDB = [
      {
        code: '3324', name: '雙鴻', market: '上櫃', sector: 'AI散熱模組', capital: 9.1,
        price: 742.0, prevClose: 708.0, open: 715.0, high: 748.0, low: 712.0, volume: 9240, volRatio: 1.86, instStreak: 6, instNet: 1420,
        desc: '高階伺服器水冷板與散熱模組領導廠・AI GPU 液冷核心供應鏈',
        pe: 26.8, peRange: [16, 22, 28, 35], grossMargin: 27.4, opMargin: 15.8, roe: 28.6, divYield: 1.65, eps4Q: 27.68, revYoY: 42.6,
        foreignHold: 24.8, instHold: 14.2, marginUsage: 28.4, dayTradePct: 44.2,
        note: '水冷快接頭與分歧管滲透率逐季拉升，營收創歷史新高，法人籌碼高度集中。'
      },
      {
        code: '3363', name: '上詮', market: '上櫃', sector: '光通訊CPO', capital: 10.2,
        price: 234.5, prevClose: 221.0, open: 223.5, high: 238.0, low: 222.0, volume: 14680, volRatio: 2.35, instStreak: 4, instNet: 1890,
        desc: '矽光子共同封裝光學 (CPO) 光纖陣列連接器關鍵技術廠',
        pe: 48.5, peRange: [25, 38, 52, 68], grossMargin: 21.6, opMargin: 8.4, roe: 11.2, divYield: 0.85, eps4Q: 4.84, revYoY: 38.9,
        foreignHold: 14.6, instHold: 8.9, marginUsage: 41.2, dayTradePct: 58.4,
        note: 'AI 算力中心高速傳輸轉向矽光子架構，CPO 產品線進入驗證放量階段。'
      },
      {
        code: '3680', name: '家登', market: '上櫃', sector: '半導體設備', capital: 9.4,
        price: 548.0, prevClose: 528.0, open: 532.0, high: 553.0, low: 529.0, volume: 4820, volRatio: 1.64, instStreak: 5, instNet: 865,
        desc: '全球 EUV 光罩盒龍頭・先進製程與 CoWoS 晶圓載具核心供應商',
        pe: 29.4, peRange: [18, 25, 32, 40], grossMargin: 46.8, opMargin: 24.1, roe: 21.5, divYield: 1.82, eps4Q: 18.64, revYoY: 31.4,
        foreignHold: 28.1, instHold: 16.5, marginUsage: 22.1, dayTradePct: 36.8,
        note: '大客戶 2 奈米試產帶動高階光罩載具需求爆發，毛利率維持 46% 以上高檔。'
      },
      {
        code: '3081', name: '聯亞', market: '上櫃', sector: '光通訊CPO', capital: 9.2,
        price: 318.0, prevClose: 304.5, open: 307.0, high: 322.5, low: 305.0, volume: 7890, volRatio: 1.78, instStreak: 3, instNet: 940,
        desc: '全球磷化銦 (InP) 雷射磊晶片大廠・800G/1.6T 高速光收發模組核心',
        pe: 44.2, peRange: [24, 35, 48, 62], grossMargin: 32.5, opMargin: 12.6, roe: 13.8, divYield: 1.10, eps4Q: 7.19, revYoY: 46.2,
        foreignHold: 31.2, instHold: 11.4, marginUsage: 34.5, dayTradePct: 51.2,
        note: '北美雲端大廠加速導入 800G 矽光模組，磊晶產能利用率顯著回升。'
      },
      {
        code: '2359', name: '所羅門', market: '上市', sector: '機器人自動化', capital: 17.1,
        price: 164.5, prevClose: 159.0, open: 160.5, high: 166.5, low: 159.5, volume: 18420, volRatio: 1.92, instStreak: 2, instNet: 1540,
        desc: '3D 機器視覺與 AI 工業機器人系統整合商・輝達機器人合作夥伴',
        pe: 38.4, peRange: [18, 28, 40, 52], grossMargin: 24.8, opMargin: 9.6, roe: 12.4, divYield: 1.45, eps4Q: 4.28, revYoY: 19.5,
        foreignHold: 15.2, instHold: 6.4, marginUsage: 38.9, dayTradePct: 54.6,
        note: 'AI 視覺辨識軟體導入物流與半導體產線，成交量能明顯放大突破盤整區。'
      },
      {
        code: '6223', name: '旺矽', market: '上櫃', sector: '半導體設備', capital: 9.4,
        price: 788.0, prevClose: 762.0, open: 768.0, high: 796.0, low: 765.0, volume: 3640, volRatio: 1.56, instStreak: 7, instNet: 680,
        desc: '全球前五大晶圓探針卡大廠・AI ASIC 與 HPC 測試介面核心受惠股',
        pe: 28.2, peRange: [15, 22, 30, 38], grossMargin: 51.2, opMargin: 26.8, roe: 27.4, divYield: 1.75, eps4Q: 27.94, revYoY: 35.1,
        foreignHold: 36.4, instHold: 18.2, marginUsage: 19.8, dayTradePct: 33.4,
        note: 'MEMS 與 VPC 垂直探針卡產能滿載，美系雲端大廠自研 AI 晶片測試訂單能見度高。'
      },
      {
        code: '3529', name: '力旺', market: '上櫃', sector: '矽智財IP', capital: 7.5,
        price: 2865.0, prevClose: 2790.0, open: 2805.0, high: 2890.0, low: 2795.0, volume: 1120, volRatio: 1.38, instStreak: 4, instNet: 215,
        desc: '全球嵌入式非揮發性記憶體 (eNVM) 矽智財霸主・權利金穩定成長',
        pe: 68.5, peRange: [45, 60, 75, 92], grossMargin: 100.0, opMargin: 56.4, roe: 52.8, divYield: 0.92, eps4Q: 41.82, revYoY: 24.8,
        foreignHold: 54.6, instHold: 12.8, marginUsage: 11.4, dayTradePct: 24.5,
        note: '3奈米與車用安全 IP 授權金持續創高，高毛利純 IP 商業模式具備強大護城河。'
      },
      {
        code: '6510', name: '精測', market: '上櫃', sector: '半導體設備', capital: 3.3,
        price: 618.0, prevClose: 602.0, open: 605.0, high: 625.0, low: 601.0, volume: 1850, volRatio: 1.52, instStreak: 3, instNet: 310,
        desc: '高階手機 AP 與 AI 伺服器晶片測試載板・探針卡全自製技術領先',
        pe: 34.6, peRange: [20, 28, 36, 45], grossMargin: 52.4, opMargin: 18.2, roe: 14.6, divYield: 1.25, eps4Q: 17.86, revYoY: 28.4,
        foreignHold: 22.8, instHold: 13.5, marginUsage: 25.6, dayTradePct: 39.2,
        note: '股本僅 3.3 億籌碼輕盈，隨 AI 伺服器測試板出貨比重拉高，毛利率重返 52% 以上。'
      },
      {
        code: '3443', name: '創意', market: '上市', sector: '矽智財IP', capital: 13.4,
        price: 1420.0, prevClose: 1395.0, open: 1405.0, high: 1435.0, low: 1390.0, volume: 2940, volRatio: 1.32, instStreak: 3, instNet: 385,
        desc: '台積電轉投資 ASIC 設計服務龍頭・HBM3e 與先進封裝客製化晶片專家',
        pe: 42.8, peRange: [28, 38, 48, 58], grossMargin: 31.8, opMargin: 19.4, roe: 29.5, divYield: 1.15, eps4Q: 33.18, revYoY: 16.4,
        foreignHold: 41.2, instHold: 15.6, marginUsage: 18.2, dayTradePct: 35.8,
        note: '北美 CSP 雲端大廠 AI ASIC 專案進入 NRE 認列與量產階段，營運逐季走高。'
      },
      {
        code: '1519', name: '華城', market: '上市', sector: '重電綠能', capital: 28.7,
        price: 684.0, prevClose: 675.0, open: 678.0, high: 691.0, low: 673.0, volume: 5420, volRatio: 1.24, instStreak: 4, instNet: 420,
        desc: '台灣超高壓變壓器出口龍頭・北美電網更新與 AI 資料中心電力受惠股',
        pe: 31.5, peRange: [18, 26, 35, 44], grossMargin: 34.2, opMargin: 21.5, roe: 32.1, divYield: 1.60, eps4Q: 21.71, revYoY: 48.2,
        foreignHold: 26.5, instHold: 11.8, marginUsage: 27.4, dayTradePct: 41.0,
        note: '外銷美國電力級變壓器訂單排程已達 2027 年，高毛利外銷比重持續攀升。'
      },
      {
        code: '6488', name: '環球晶', market: '上櫃', sector: '半導體設備', capital: 47.8,
        price: 462.0, prevClose: 456.5, open: 458.0, high: 466.0, low: 455.0, volume: 3180, volRatio: 1.15, instStreak: 2, instNet: 290,
        desc: '全球前三大半導體矽晶圓製造商・12吋先進製程與化合物半導體佈局完整',
        pe: 18.6, peRange: [14, 19, 25, 31], grossMargin: 33.6, opMargin: 23.8, roe: 19.2, divYield: 3.15, eps4Q: 24.84, revYoY: 6.8,
        foreignHold: 38.4, instHold: 14.1, marginUsage: 16.5, dayTradePct: 22.4,
        note: '本益比處於歷史合理偏低區間，具備高殖利率保護與先進製程矽晶圓復甦題材。'
      },
      {
        code: '8069', name: '元太', market: '上櫃', sector: 'IC設計', capital: 114.6,
        price: 278.5, prevClose: 276.0, open: 277.0, high: 281.5, low: 275.5, volume: 8920, volRatio: 1.18, instStreak: 5, instNet: 1120,
        desc: '全球電子紙 (E-Ink) 技術壟斷龍頭・彩色電子書閱讀器與零售電子標籤升級潮',
        pe: 31.2, peRange: [20, 27, 34, 42], grossMargin: 49.6, opMargin: 27.4, roe: 21.0, divYield: 1.80, eps4Q: 8.93, revYoY: 22.4,
        foreignHold: 44.8, instHold: 16.2, marginUsage: 15.4, dayTradePct: 25.8,
        note: '大型零售通路導入四色電子貨架標籤 (ESL)，外資與投信同步偏多加碼。'
      },
      {
        code: '4966', name: '譜瑞-KY', market: '上櫃', sector: 'IC設計', capital: 8.1,
        price: 836.0, prevClose: 842.0, open: 840.0, high: 848.0, low: 829.0, volume: 1420, volRatio: 0.94, instStreak: 0, instNet: -115,
        desc: '高速傳輸介面晶片領導廠・PCIe Gen5/Gen6 Retimer 與 USB4 關鍵供應商',
        pe: 25.4, peRange: [18, 24, 30, 38], grossMargin: 43.5, opMargin: 21.2, roe: 22.8, divYield: 2.05, eps4Q: 32.91, revYoY: 14.2,
        foreignHold: 48.2, instHold: 13.9, marginUsage: 14.8, dayTradePct: 26.1,
        note: 'AI PC 換機潮帶動 USB4 與高速訊號中繼器出貨回溫，股本小具高 EPS 爆發力。'
      },
      {
        code: '3293', name: '鈊象', market: '上櫃', sector: '生技新藥', capital: 28.2,
        price: 985.0, prevClose: 992.0, open: 990.0, high: 998.0, low: 978.0, volume: 1960, volRatio: 0.92, instStreak: 0, instNet: -85,
        desc: '台灣商用遊戲機與線上博弈授權龍頭・東南亞與歐美授權金高成長',
        pe: 23.8, peRange: [16, 22, 28, 34], grossMargin: 96.4, opMargin: 54.2, roe: 48.5, divYield: 3.55, eps4Q: 41.38, revYoY: 26.8,
        foreignHold: 39.5, instHold: 14.8, marginUsage: 12.6, dayTradePct: 21.4,
        note: '毛利率高達 96% 的高現金流績優股，高股息殖利率具備防禦與成長雙重優勢。'
      },
      {
        code: '3105', name: '穩懋', market: '上櫃', sector: 'IC設計', capital: 42.4,
        price: 148.5, prevClose: 150.0, open: 150.5, high: 151.5, low: 147.0, volume: 6840, volRatio: 0.88, instStreak: 0, instNet: -420,
        desc: '全球最大砷化鎵 (GaAs) 晶圓代工廠・Wi-Fi 7 PA 與低軌衛星通訊核心廠',
        pe: 29.8, peRange: [20, 28, 38, 48], grossMargin: 25.2, opMargin: 9.8, roe: 8.4, divYield: 1.35, eps4Q: 4.98, revYoY: 11.5,
        foreignHold: 32.1, instHold: 7.6, marginUsage: 31.2, dayTradePct: 37.5,
        note: 'Wi-Fi 7 滲透率提升帶動功率放大器需求，短線回測月線尋求支撐。'
      },
      {
        code: '6472', name: '保瑞', market: '上市', sector: '生技新藥', capital: 10.4,
        price: 795.0, prevClose: 808.0, open: 805.0, high: 812.0, low: 788.0, volume: 2480, volRatio: 1.05, instStreak: 0, instNet: -195,
        desc: '台灣最大國際級 CDMO 委託開發暨製造藥廠・併購美國無菌針劑廠綜效顯現',
        pe: 19.4, peRange: [15, 21, 28, 36], grossMargin: 44.8, opMargin: 28.5, roe: 34.2, divYield: 1.50, eps4Q: 40.98, revYoY: 34.6,
        foreignHold: 27.4, instHold: 15.1, marginUsage: 21.8, dayTradePct: 34.2,
        note: '美國 Upsher-Smith 併表帶動營收跳增，本益比低於 20 倍具中長線價值。'
      }
    ];

    // 合併所有個股以便第二層終端通用查詢
    const allStocksDB = [...heavyweightStocksDB, ...smallCapStocksDB];

    // =========================================================================
    // 2. 確定性隨機數與時間序列產生器 (大盤 + 個股多週期 K 線)
    // =========================================================================
    function seededRandom(seed) {
      let s = seed % 2147483647;
      if (s <= 0) s += 2147483646;
      return function() {
        s = (s * 16807) % 2147483647;
        return (s - 1) / 2147483646;
      };
    }

    function buildMultiTimeframeSeries(obj, seedVal, baseVol, isIndex = false) {
      const rand = seededRandom(seedVal);
      const dec = isIndex ? 2 : 1;

      // 1) 即時分時走勢 (09:00 ~ 13:30 共 135 點)
      const intraday = [];
      let curP = obj.open;
      let cumPV = 0, cumV = 0;
      const pts = 135;
      for (let i = 0; i < pts; i++) {
        const prog = i / (pts - 1);
        const target = obj.open + (obj.price - obj.open) * prog;
        const noise = (rand() - 0.48) * obj.prevClose * (isIndex ? 0.0014 : 0.0045);
        curP = i === pts - 1 ? obj.price : Math.max(obj.low, Math.min(obj.high, curP * 0.68 + target * 0.32 + noise));
        const v = Math.max(1, Number(((baseVol / pts) * (0.45 + rand() * 1.5)).toFixed(isIndex ? 1 : 0)));
        cumPV += curP * v;
        cumV += v;
        const mins = i * 2;
        const label = `${String(9 + Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
        intraday.push({
          label,
          open: Number(curP.toFixed(dec)),
          high: Number(curP.toFixed(dec)),
          low: Number(curP.toFixed(dec)),
          close: Number(curP.toFixed(dec)),
          vwap: Number((cumPV / cumV).toFixed(dec)),
          volume: v
        });
      }

      // 2) 各週期 K 線
      function makeCandles(count, volMult, drift, isWeekly = false) {
        const arr = [];
        let p = obj.price * ((obj.price >= obj.prevClose) ? (isIndex ? 0.90 : 0.78) : 1.12);
        const now = new Date(2026, 10, 17);
        for (let i = 0; i < count; i++) {
          const isLast = i === count - 1;
          const d = new Date(now);
          d.setDate(d.getDate() - (count - 1 - i) * (isWeekly ? 7 : 1));
          const label = `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
          if (isLast) {
            arr.push({
              label,
              open: obj.open,
              high: obj.high,
              low: obj.low,
              close: obj.price,
              volume: baseVol
            });
          } else {
            const stepTarget = p + (obj.price - p) / (count - i);
            const open = Number(p.toFixed(dec));
            const move = (stepTarget - p) * 0.55 + (rand() - 0.48) * p * drift;
            const close = Number(Math.max(10, open + move).toFixed(dec));
            const high = Number((Math.max(open, close) * (1 + rand() * drift * 0.65)).toFixed(dec));
            const low = Number((Math.min(open, close) * (1 - rand() * drift * 0.65)).toFixed(dec));
            const volume = Math.max(10, Number((baseVol * volMult * (0.5 + rand() * 1.15)).toFixed(isIndex ? 1 : 0)));
            arr.push({ label, open, high, low, close, volume });
            p = close;
          }
        }
        return arr;
      }

      obj.series = {
        intraday,
        '1m':  makeCandles(110, 0.03, isIndex ? 0.0018 : 0.004),
        '5m':  makeCandles(110, 0.08, isIndex ? 0.0035 : 0.008),
        '15m': makeCandles(110, 0.16, isIndex ? 0.0055 : 0.013),
        '60m': makeCandles(110, 0.35, isIndex ? 0.0085 : 0.020),
        '1d':  makeCandles(120, 1.00, isIndex ? 0.0120 : 0.032),
        '1w':  makeCandles(90,  4.50, isIndex ? 0.0240 : 0.058, true)
      };
    }

    function initAllData() {
      // 初始化加權與櫃買指數序列
      buildMultiTimeframeSeries(macroIndices.TAIEX, 20261117, macroIndices.TAIEX.turnover, true);
      buildMultiTimeframeSeries(macroIndices.OTC,   20260888, macroIndices.OTC.turnover, true);

      // 初始化所有個股序列、法人與營收資料
      allStocksDB.forEach(s => {
        s.change = Number((s.price - s.prevClose).toFixed(2));
        s.changePct = Number(((s.change / s.prevClose) * 100).toFixed(2));
        buildMultiTimeframeSeries(s, parseInt(s.code, 10) * 137, s.volume, false);

        const rand = seededRandom(parseInt(s.code, 10) * 293);
        // 近 15 日三大法人
        s.instHistory = [];
        for (let i = 14; i >= 0; i--) {
          const d = new Date(2026, 10, 17);
          d.setDate(d.getDate() - i);
          const dateStr = `${d.getMonth() + 1}/${d.getDate()}`;
          const bias = s.instNet >= 0 ? 0.35 : -0.35;
          const scale = Math.max(120, Math.abs(s.instNet) * 0.85);
          const foreign = i === 0 ? Math.round(s.instNet * 0.65) : Math.round((rand() - 0.5 + bias) * scale);
          const trust   = i === 0 ? Math.round(s.instNet * 0.30) : Math.round((rand() - 0.45 + bias) * scale * 0.55);
          const dealer  = i === 0 ? (s.instNet - foreign - trust) : Math.round((rand() - 0.5) * scale * 0.35);
          s.instHistory.push({ date: dateStr, foreign, trust, dealer });
        }

        // 主力前五大買賣超分點
        const brokers = ['凱基-台北', '摩根大通', '元大-館前', '美林證券', '富邦-建國', '瑞銀台北', '高盛證券', '永豐金-竹科', '群益-大安', '國泰-敦南'];
        s.buyBrokers = [];
        s.sellBrokers = [];
        for (let i = 0; i < 5; i++) {
          s.buyBrokers.push({
            name: brokers[i],
            lots: Math.max(30, Math.round((160 + rand() * 580) * (s.volume / 5500))),
            avgPrice: Number((s.price * (0.992 + rand() * 0.008)).toFixed(1))
          });
          s.sellBrokers.push({
            name: brokers[i + 5],
            lots: Math.max(25, Math.round((140 + rand() * 510) * (s.volume / 5500))),
            avgPrice: Number((s.price * (0.995 + rand() * 0.01)).toFixed(1))
          });
        }

        // 近 12 個月合併營收與 YoY
        s.revenueHistory = [];
        const baseRev = Number((s.capital * (1.7 + rand() * 2.2)).toFixed(2));
        for (let m = 11; m >= 0; m--) {
          const d = new Date(2026, 9 - m, 1);
          const ym = `${String(d.getFullYear()).slice(2)}/${String(d.getMonth() + 1).padStart(2, '0')}`;
          const growth = 1 + ((11 - m) / 11) * (s.revYoY / 100) * 0.55;
          const rev = Number((baseRev * growth * (0.9 + rand() * 0.2)).toFixed(2));
          const yoy = m === 0 ? s.revYoY : Number((s.revYoY * (0.65 + rand() * 0.65)).toFixed(1));
          s.revenueHistory.push({ ym, rev, yoy });
        }
      });
    }

    // =========================================================================
    // 3. 技術指標數學引擎 (MA, Bollinger, MACD, KD, RSI)
    // =========================================================================
    function calcSMA(data, period) {
      return data.map((_, idx) => {
        if (idx < period - 1) return null;
        let sum = 0;
        for (let j = 0; j < period; j++) sum += data[idx - j].close;
        return sum / period;
      });
    }

    function calcBollinger(data, period = 20, mult = 2) {
      const mid = calcSMA(data, period);
      return data.map((_, idx) => {
        if (idx < period - 1) return { upper: null, mid: null, lower: null };
        let sqSum = 0;
        for (let j = 0; j < period; j++) {
          const diff = data[idx - j].close - mid[idx];
          sqSum += diff * diff;
        }
        const std = Math.sqrt(sqSum / period);
        return { upper: mid[idx] + mult * std, mid: mid[idx], lower: mid[idx] - mult * std };
      });
    }

    function calcMACD(data, fast = 12, slow = 26, sig = 9) {
      const kFast = 2 / (fast + 1), kSlow = 2 / (slow + 1), kSig = 2 / (sig + 1);
      let emaFast = data[0]?.close || 0, emaSlow = data[0]?.close || 0, dem = 0;
      return data.map((d, idx) => {
        if (idx > 0) {
          emaFast = d.close * kFast + emaFast * (1 - kFast);
          emaSlow = d.close * kSlow + emaSlow * (1 - kSlow);
        }
        const dif = emaFast - emaSlow;
        dem = idx === 0 ? dif : dif * kSig + dem * (1 - kSig);
        return { dif, dem, osc: dif - dem };
      });
    }

    function calcKD(data, period = 9) {
      let k = 50, d = 50;
      return data.map((item, idx) => {
        const start = Math.max(0, idx - period + 1);
        let highest = -Infinity, lowest = Infinity;
        for (let j = start; j <= idx; j++) {
          if (data[j].high > highest) highest = data[j].high;
          if (data[j].low < lowest) lowest = data[j].low;
        }
        const rsv = highest === lowest ? 50 : ((item.close - lowest) / (highest - lowest)) * 100;
        k = (2 / 3) * k + (1 / 3) * rsv;
        d = (2 / 3) * d + (1 / 3) * k;
        return { k, d };
      });
    }

    function calcRSI(data, period) {
      let avgGain = 0, avgLoss = 0;
      return data.map((item, idx) => {
        if (idx === 0) return 50;
        const diff = item.close - data[idx - 1].close;
        const gain = diff > 0 ? diff : 0;
        const loss = diff < 0 ? -diff : 0;
        if (idx <= period) {
          avgGain = (avgGain * (idx - 1) + gain) / idx;
          avgLoss = (avgLoss * (idx - 1) + loss) / idx;
        } else {
          avgGain = (avgGain * (period - 1) + gain) / period;
          avgLoss = (avgLoss * (period - 1) + loss) / period;
        }
        if (avgLoss === 0) return 100;
        return 100 - 100 / (1 + avgGain / avgLoss);
      });
    }

    // =========================================================================
    // 4. 麵包屑導航與全域搜尋
    // =========================================================================
    function updateBreadcrumbs() {
      const cMarket = document.getElementById('crumbMarket');
      const cScreener = document.getElementById('crumbScreener');
      const cStock = document.getElementById('crumbStock');
      const s = getCurrentStock();
      document.getElementById('crumbStockLabel').textContent = `${s.code} ${s.name}`;

      const activeCls = 'flex items-center gap-1 px-2.5 py-1 rounded-lg font-semibold transition bg-red-500/20 text-red-300 border border-red-500/40';
      const inactiveCls = 'flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition text-[#848e9c] hover:text-white hover:bg-[#192030] border border-transparent';

      cMarket.className = state.view === 'market' ? activeCls : inactiveCls;
      cScreener.className = inactiveCls;
      cStock.className = state.view === 'stock' ? activeCls : inactiveCls;
    }

    function navigateTo(target) {
      if (target === 'market') {
        state.view = 'market';
        document.getElementById('viewMarket').classList.remove('hidden');
        document.getElementById('viewStock').classList.add('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        renderHeroIndexChart();
      } else if (target === 'screener') {
        state.view = 'market';
        document.getElementById('viewMarket').classList.remove('hidden');
        document.getElementById('viewStock').classList.add('hidden');
        renderHeroIndexChart();
        setTimeout(() => document.getElementById('screenerSection').scrollIntoView({ behavior: 'smooth' }), 50);
      } else if (target === 'stock') {
        drillDownStock(state.selectedStockCode);
      }
      updateBreadcrumbs();
    }

    // 即時搜尋框
    const searchInput = document.getElementById('globalSearchInput');
    const searchDropdown = document.getElementById('searchDropdown');
    const clearSearchBtn = document.getElementById('clearSearchBtn');

    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.trim().toLowerCase();
      clearSearchBtn.classList.toggle('hidden', q.length === 0);
      if (!q) { searchDropdown.classList.add('hidden'); return; }

      const matches = allStocksDB.filter(s =>
        s.code.includes(q) || s.name.toLowerCase().includes(q) || s.sector.toLowerCase().includes(q)
      );
      if (matches.length === 0) {
        searchDropdown.innerHTML = `<div class="p-3 text-xs text-[#848e9c] text-center">找不到符合「${e.target.value}」的標的</div>`;
      } else {
        searchDropdown.innerHTML = matches.map(s => {
          const isUp = s.change >= 0;
          const col = isUp ? 'text-red-400' : 'text-emerald-400';
          return `
            <button onclick="drillDownStock('${s.code}'); clearSearch();" class="w-full px-3 py-2.5 flex items-center justify-between hover:bg-[#192030] border-b border-[#262d3d]/50 last:border-none text-left transition">
              <div>
                <div class="text-xs font-bold text-white">${s.code} ${s.name} <span class="text-[10px] font-normal px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-300 ml-1">${s.sector}</span></div>
                <div class="text-[10px] text-[#848e9c]">${s.market}・股本 ${s.capital} 億</div>
              </div>
              <div class="text-right tabular-nums">
                <div class="text-xs font-bold ${col}">${s.price.toFixed(1)}</div>
                <div class="text-[10px] ${col}">${isUp ? '+' : ''}${s.changePct.toFixed(2)}%</div>
              </div>
            </button>
          `;
        }).join('');
      }
      searchDropdown.classList.remove('hidden');
    });

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) searchDropdown.classList.add('hidden');
    });

    function clearSearch() {
      searchInput.value = '';
      clearSearchBtn.classList.add('hidden');
      searchDropdown.classList.add('hidden');
    }

    // =========================================================================
    // 5. VIEW 1: 台灣加權指數 (Hero Section) 核心報價、大型互動圖表、權值貢獻與雷達
    // =========================================================================
    function switchHeroIndex(key) {
      state.heroIndexKey = key;
      state.heroChart.offsetBars = 0;
      state.heroChart.hoverIndex = -1;
      document.getElementById('heroSwitchToTaiexBtn').classList.toggle('hidden', key === 'TAIEX');
      updateHeroIndexHeader();
      renderHeroIndexChart();
    }

    function updateHeroIndexHeader() {
      const idx = macroIndices[state.heroIndexKey];
      const chg = idx.price - idx.prevClose;
      const pct = (chg / idx.prevClose) * 100;
      const isUp = chg >= 0;
      const col = isUp ? 'text-red-400' : 'text-emerald-400';

      document.getElementById('heroIndexTitle').innerHTML = `${idx.name} <span class="font-mono text-sm font-semibold text-[#848e9c]">${idx.code}</span>`;
      const pEl = document.getElementById('heroIndexPrice');
      pEl.textContent = idx.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      pEl.className = `text-4xl sm:text-5xl font-black ${col} tracking-tight`;

      const cEl = document.getElementById('heroIndexChange');
      cEl.textContent = `${isUp ? '▲ +' : '▼ '}${chg.toFixed(2)}`;
      cEl.className = col;

      const pctEl = document.getElementById('heroIndexChangePct');
      pctEl.textContent = `${isUp ? '+' : ''}${pct.toFixed(2)}%`;
      pctEl.className = isUp
        ? 'px-2 py-0.5 rounded-md bg-red-500/15 border border-red-500/30 text-sm sm:text-base text-red-400'
        : 'px-2 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-sm sm:text-base text-emerald-400';

      document.getElementById('heroIndexOpen').textContent = idx.open.toLocaleString('en-US', { minimumFractionDigits: 2 });
      document.getElementById('heroIndexOpen').className = `font-bold text-sm ${idx.open >= idx.prevClose ? 'text-red-400' : 'text-emerald-400'}`;
      document.getElementById('heroIndexHigh').textContent = idx.high.toLocaleString('en-US', { minimumFractionDigits: 2 });
      document.getElementById('heroIndexLow').textContent = idx.low.toLocaleString('en-US', { minimumFractionDigits: 2 });
      document.getElementById('heroIndexPrev').textContent = idx.prevClose.toLocaleString('en-US', { minimumFractionDigits: 2 });
      document.getElementById('heroIndexTurnover').textContent = `${idx.turnover.toFixed(1)} 億`;

      // 同步更新右側櫃買指數快捷卡
      const otc = macroIndices.OTC;
      const otcChg = otc.price - otc.prevClose;
      const otcPct = (otcChg / otc.prevClose) * 100;
      const otcUp = otcChg >= 0;
      document.getElementById('otcCardPrice').textContent = otc.price.toFixed(2);
      document.getElementById('otcCardPrice').className = `text-2xl font-black ${otcUp ? 'text-red-400' : 'text-emerald-400'}`;
      document.getElementById('otcCardChange').textContent = `${otcUp ? '▲ +' : '▼ '}${otcChg.toFixed(2)} (${otcUp ? '+' : ''}${otcPct.toFixed(2)}%)`;
      document.getElementById('otcCardChange').className = `text-xs font-bold ${otcUp ? 'text-red-400' : 'text-emerald-400'}`;
    }

    function setHeroTimeframe(tf) {
      state.heroChart.timeframe = tf;
      state.heroChart.offsetBars = 0;
      state.heroChart.hoverIndex = -1;
      document.querySelectorAll('.htf-btn').forEach(btn => {
        btn.className = btn.id === `htf_${tf}`
          ? 'htf-btn px-2.5 py-1 text-xs rounded-md font-semibold bg-red-600 text-white transition'
          : 'htf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition';
      });
      renderHeroIndexChart();
    }

    function toggleHeroOverlay(key) {
      state.heroChart.overlays[key] = !state.heroChart.overlays[key];
      const active = state.heroChart.overlays[key];
      const styles = {
        MA5:  'bg-amber-500/20 text-amber-300 border-amber-500/40',
        MA10: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
        MA20: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
        MA60: 'bg-pink-500/20 text-pink-300 border-pink-500/40',
        BOLL: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
      };
      const el = document.getElementById(`hov_${key}`);
      el.className = active
        ? `px-2 py-1 rounded border font-mono transition ${styles[key]}`
        : 'px-2 py-1 rounded border font-mono transition bg-[#0a0d12] text-[#848e9c] border-[#262d3d]';
      renderHeroIndexChart();
    }

    function setHeroSubIndicator(ind) {
      state.heroChart.subIndicator = ind;
      ['VOL', 'MACD', 'KD'].forEach(k => {
        const el = document.getElementById(`hsub_${k}`);
        el.className = k === ind
          ? 'px-2.5 py-1 rounded-md font-medium bg-blue-600 text-white transition'
          : 'px-2.5 py-1 rounded-md font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition';
      });
      renderHeroIndexChart();
    }

    function zoomHeroChart(factor) {
      state.heroChart.visibleBars = Math.max(20, Math.min(120, Math.round(state.heroChart.visibleBars * factor)));
      renderHeroIndexChart();
    }

    function resetHeroZoom() {
      state.heroChart.visibleBars = 65;
      state.heroChart.offsetBars = 0;
      renderHeroIndexChart();
    }

    // 繪製首屏大型台灣加權指數 Canvas 圖表
    function renderHeroIndexChart() {
      const canvas = document.getElementById('heroIndexCanvas');
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);

      const W = rect.width, H = rect.height;
      const padL = 12, padR = 68, padT = 14, padB = 24;
      const plotW = W - padL - padR;
      const plotH = H - padT - padB;
      const mainH = plotH * 0.70;
      const subTop = padT + mainH + plotH * 0.05;
      const subH = plotH * 0.25;

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#0a0d12';
      ctx.fillRect(0, 0, W, H);

      const idxObj = macroIndices[state.heroIndexKey];
      const tf = state.heroChart.timeframe;
      const fullSeries = idxObj.series[tf] || idxObj.series['intraday'];
      const isIntraday = tf === 'intraday';
      const dec = state.heroIndexKey === 'OTC' ? 2 : 0;

      const ma5All = calcSMA(fullSeries, 5);
      const ma10All = calcSMA(fullSeries, 10);
      const ma20All = calcSMA(fullSeries, 20);
      const ma60All = calcSMA(fullSeries, 60);
      const bollAll = calcBollinger(fullSeries, 20, 2);
      const macdAll = calcMACD(fullSeries);
      const kdAll = calcKD(fullSeries);

      const total = fullSeries.length;
      const visCount = isIntraday ? total : Math.min(total, state.heroChart.visibleBars);
      const maxOffset = Math.max(0, total - visCount);
      state.heroChart.offsetBars = Math.max(0, Math.min(maxOffset, state.heroChart.offsetBars));
      const endIdx = total - state.heroChart.offsetBars;
      const startIdx = Math.max(0, endIdx - visCount);
      const slice = fullSeries.slice(startIdx, endIdx);

      let minP = Infinity, maxP = -Infinity;
      slice.forEach((c, i) => {
        const gIdx = startIdx + i;
        let hi = isIntraday ? Math.max(c.close, c.vwap, idxObj.prevClose) : c.high;
        let lo = isIntraday ? Math.min(c.close, c.vwap, idxObj.prevClose) : c.low;
        if (!isIntraday && state.heroChart.overlays.BOLL && bollAll[gIdx].upper !== null) {
          hi = Math.max(hi, bollAll[gIdx].upper);
          lo = Math.min(lo, bollAll[gIdx].lower);
        }
        if (hi > maxP) maxP = hi;
        if (lo < minP) minP = lo;
      });
      const pSpan = Math.max(0.5, maxP - minP);
      minP -= pSpan * 0.06;
      maxP += pSpan * 0.06;

      const yMain = (p) => padT + ((maxP - p) / (maxP - minP)) * mainH;
      const xBar = (i) => padL + ((i + 0.5) / slice.length) * plotW;
      const barW = Math.max(2, (plotW / slice.length) * 0.65);

      // 水平網格與右側點數刻度
      ctx.strokeStyle = '#1b2232';
      ctx.lineWidth = 1;
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#848e9c';
      ctx.textAlign = 'left';
      for (let g = 0; g <= 4; g++) {
        const y = padT + (g / 4) * mainH;
        const val = maxP - (g / 4) * (maxP - minP);
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(W - padR, y);
        ctx.stroke();
        ctx.fillText(val.toFixed(dec), W - padR + 6, y + 3);
      }

      if (isIntraday) {
        // 昨收基準虛線
        const prevY = yMain(idxObj.prevClose);
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = '#64748b';
        ctx.beginPath();
        ctx.moveTo(padL, prevY);
        ctx.lineTo(W - padR, prevY);
        ctx.stroke();
        ctx.restore();

        const isUp = idxObj.price >= idxObj.prevClose;
        const lineCol = isUp ? '#ef4444' : '#10b981';
        const grad = ctx.createLinearGradient(0, padT, 0, padT + mainH);
        grad.addColorStop(0, isUp ? 'rgba(239,68,68,0.32)' : 'rgba(16,185,129,0.32)');
        grad.addColorStop(1, 'rgba(10,13,18,0)');

        ctx.beginPath();
        slice.forEach((pt, i) => {
          const x = xBar(i), y = yMain(pt.close);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = lineCol;
        ctx.lineWidth = 2.2;
        ctx.stroke();

        ctx.lineTo(xBar(slice.length - 1), padT + mainH);
        ctx.lineTo(xBar(0), padT + mainH);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

        // 委買均價線 (VWAP 黃線)
        ctx.beginPath();
        slice.forEach((pt, i) => {
          const x = xBar(i), y = yMain(pt.vwap);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 1.6;
        ctx.stroke();
      } else {
        // 布林通道
        if (state.heroChart.overlays.BOLL) {
          ctx.fillStyle = 'rgba(99, 102, 241, 0.08)';
          ctx.beginPath();
          let first = true;
          slice.forEach((_, i) => {
            const b = bollAll[startIdx + i];
            if (b.upper === null) return;
            const x = xBar(i), y = yMain(b.upper);
            if (first) { ctx.moveTo(x, y); first = false; }
            else ctx.lineTo(x, y);
          });
          for (let i = slice.length - 1; i >= 0; i--) {
            const b = bollAll[startIdx + i];
            if (b.lower !== null) ctx.lineTo(xBar(i), yMain(b.lower));
          }
          ctx.closePath();
          ctx.fill();
        }

        // 大盤 K 棒
        slice.forEach((c, i) => {
          const x = xBar(i);
          const isUp = c.close >= c.open;
          const col = isUp ? '#ef4444' : '#10b981';
          ctx.strokeStyle = col;
          ctx.fillStyle = col;
          ctx.lineWidth = 1.2;

          ctx.beginPath();
          ctx.moveTo(x, yMain(c.high));
          ctx.lineTo(x, yMain(c.low));
          ctx.stroke();

          const topY = yMain(Math.max(c.open, c.close));
          const botY = yMain(Math.min(c.open, c.close));
          ctx.fillRect(x - barW / 2, topY, barW, Math.max(1.8, botY - topY));
        });

        // 疊加均線
        [
          { key: 'MA5',  arr: ma5All,  col: '#f59e0b' },
          { key: 'MA10', arr: ma10All, col: '#c084fc' },
          { key: 'MA20', arr: ma20All, col: '#22d3ee' },
          { key: 'MA60', arr: ma60All, col: '#f472b6' }
        ].forEach(cfg => {
          if (!state.heroChart.overlays[cfg.key]) return;
          ctx.beginPath();
          let started = false;
          slice.forEach((_, i) => {
            const v = cfg.arr[startIdx + i];
            if (v === null) return;
            const x = xBar(i), y = yMain(v);
            if (!started) { ctx.moveTo(x, y); started = true; }
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = cfg.col;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        });
      }

      // 現價右側標籤
      const lastY = yMain(idxObj.price);
      ctx.fillStyle = idxObj.price >= idxObj.prevClose ? '#ef4444' : '#10b981';
      ctx.fillRect(W - padR + 2, lastY - 8, padR - 4, 16);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 10px "JetBrains Mono", monospace';
      ctx.fillText(idxObj.price.toFixed(dec), W - padR + 5, lastY + 3);

      // 副圖區
      ctx.strokeStyle = '#262d3d';
      ctx.beginPath();
      ctx.moveTo(padL, subTop - 4);
      ctx.lineTo(W - padR, subTop - 4);
      ctx.stroke();

      const subInd = state.heroChart.subIndicator;
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#848e9c';

      if (subInd === 'VOL') {
        const maxV = Math.max(...slice.map(c => c.volume), 1);
        ctx.fillText(`${maxV.toFixed(0)}億`, W - padR + 6, subTop + 8);
        slice.forEach((c, i) => {
          const prev = i > 0 ? slice[i - 1].close : idxObj.prevClose;
          const isUp = isIntraday ? c.close >= prev : c.close >= c.open;
          ctx.fillStyle = isUp ? 'rgba(239, 68, 68, 0.75)' : 'rgba(16, 185, 129, 0.75)';
          const h = (c.volume / maxV) * subH;
          ctx.fillRect(xBar(i) - barW / 2, subTop + subH - h, barW, h);
        });
      } else if (subInd === 'MACD') {
        const mSlice = macdAll.slice(startIdx, endIdx);
        const absMax = Math.max(...mSlice.map(m => Math.max(Math.abs(m.dif), Math.abs(m.dem), Math.abs(m.osc))), 0.1);
        const zeroY = subTop + subH / 2;
        ctx.fillText(`+${absMax.toFixed(0)}`, W - padR + 6, subTop + 8);
        mSlice.forEach((m, i) => {
          const h = (m.osc / absMax) * (subH / 2);
          ctx.fillStyle = m.osc >= 0 ? 'rgba(239,68,68,0.75)' : 'rgba(16,185,129,0.75)';
          if (h >= 0) ctx.fillRect(xBar(i) - barW / 2, zeroY - h, barW, h);
          else ctx.fillRect(xBar(i) - barW / 2, zeroY, barW, -h);
        });
        [
          { key: 'dif', col: '#f59e0b' },
          { key: 'dem', col: '#22d3ee' }
        ].forEach(l => {
          ctx.beginPath();
          mSlice.forEach((m, i) => {
            const x = xBar(i), y = zeroY - (m[l.key] / absMax) * (subH / 2);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = l.col;
          ctx.lineWidth = 1.4;
          ctx.stroke();
        });
      } else if (subInd === 'KD') {
        const kdSlice = kdAll.slice(startIdx, endIdx);
        const yKD = (v) => subTop + ((100 - v) / 100) * subH;
        ctx.fillText('80', W - padR + 6, yKD(80) + 3);
        ctx.fillText('20', W - padR + 6, yKD(20) + 3);
        [
          { key: 'k', col: '#f59e0b' },
          { key: 'd', col: '#22d3ee' }
        ].forEach(l => {
          ctx.beginPath();
          kdSlice.forEach((item, i) => {
            const x = xBar(i), y = yKD(item[l.key]);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = l.col;
          ctx.lineWidth = 1.4;
          ctx.stroke();
        });
      }

      // X 軸時間刻度
      ctx.fillStyle = '#848e9c';
      ctx.textAlign = 'center';
      const step = Math.max(1, Math.floor(slice.length / 5));
      for (let i = 0; i < slice.length; i += step) {
        ctx.fillText(slice[i].label, xBar(i), H - 6);
      }

      // 十字線與頂部即時讀數列
      const activeLocal = (state.heroChart.hoverIndex >= 0 && state.heroChart.hoverIndex < slice.length)
        ? state.heroChart.hoverIndex
        : slice.length - 1;
      const activeGlobal = startIdx + activeLocal;
      const bar = slice[activeLocal];

      if (state.heroChart.hoverIndex >= 0 && state.heroChart.hoverIndex < slice.length) {
        const cx = xBar(activeLocal);
        const cy = yMain(bar.close);
        ctx.save();
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = '#94a3b8';
        ctx.beginPath();
        ctx.moveTo(cx, padT);
        ctx.lineTo(cx, subTop + subH);
        ctx.moveTo(padL, cy);
        ctx.lineTo(W - padR, cy);
        ctx.stroke();
        ctx.restore();
      }

      const readoutEl = document.getElementById('heroChartReadoutBar');
      const chgPct = (((bar.close - idxObj.prevClose) / idxObj.prevClose) * 100).toFixed(2);
      const col = bar.close >= idxObj.prevClose ? 'text-red-400' : 'text-emerald-400';

      if (isIntraday) {
        readoutEl.innerHTML = `
          <div class="flex flex-wrap items-center gap-3">
            <span class="text-white font-semibold">時間 ${bar.label}</span>
            <span>指數 <b class="${col}">${bar.close.toFixed(2)}</b> (<span class="${col}">${chgPct >= 0 ? '+' : ''}${chgPct}%</span>)</span>
            <span class="text-amber-400">● 委買均價線 (VWAP): <b>${bar.vwap.toFixed(2)}</b></span>
            <span>區間成交 <b class="text-slate-200">${bar.volume} 億</b></span>
          </div>
          <span class="text-[#848e9c] hidden sm:inline">灰虛線：昨收基準 (${idxObj.prevClose.toFixed(2)})</span>
        `;
      } else {
        const m5v = ma5All[activeGlobal] ? ma5All[activeGlobal].toFixed(1) : '--';
        const m10v = ma10All[activeGlobal] ? ma10All[activeGlobal].toFixed(1) : '--';
        const m20v = ma20All[activeGlobal] ? ma20All[activeGlobal].toFixed(1) : '--';
        readoutEl.innerHTML = `
          <div class="flex flex-wrap items-center gap-2.5">
            <span class="text-white font-semibold">${bar.label}</span>
            <span>開 <b class="text-slate-200">${bar.open.toFixed(1)}</b></span>
            <span>高 <b class="text-red-400">${bar.high.toFixed(1)}</b></span>
            <span>低 <b class="text-emerald-400">${bar.low.toFixed(1)}</b></span>
            <span>收 <b class="${col}">${bar.close.toFixed(1)}</b></span>
            <span>成交 <b class="text-amber-300">${bar.volume.toFixed(1)}億</b></span>
          </div>
          <div class="flex items-center gap-2.5">
            <span class="text-amber-400">MA5:${m5v}</span>
            <span class="text-purple-400">MA10:${m10v}</span>
            <span class="text-cyan-400">MA20:${m20v}</span>
          </div>
        `;
      }
    }

    function initHeroCanvasInteractions() {
      const canvas = document.getElementById('heroIndexCanvas');
      canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (state.heroChart.timeframe === 'intraday') return;
        zoomHeroChart(e.deltaY > 0 ? 1.15 : 0.85);
      }, { passive: false });

      canvas.addEventListener('mousedown', (e) => {
        if (state.heroChart.timeframe === 'intraday') return;
        state.heroChart.isDragging = true;
        state.heroChart.dragStartX = e.clientX;
        state.heroChart.dragStartOffset = state.heroChart.offsetBars;
        canvas.classList.add('grabbing');
      });

      window.addEventListener('mouseup', () => {
        state.heroChart.isDragging = false;
        canvas.classList.remove('grabbing');
      });

      canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const plotW = rect.width - 80;
        const idxObj = macroIndices[state.heroIndexKey];
        const fullLen = (idxObj.series[state.heroChart.timeframe] || idxObj.series['intraday']).length;
        const visCount = state.heroChart.timeframe === 'intraday' ? fullLen : Math.min(fullLen, state.heroChart.visibleBars);

        if (state.heroChart.isDragging) {
          const dx = e.clientX - state.heroChart.dragStartX;
          const barDelta = Math.round((dx / plotW) * visCount);
          state.heroChart.offsetBars = Math.max(0, Math.min(fullLen - visCount, state.heroChart.dragStartOffset + barDelta));
          renderHeroIndexChart();
          return;
        }
        const x = e.clientX - rect.left - 12;
        state.heroChart.hoverIndex = Math.max(0, Math.min(visCount - 1, Math.floor((x / plotW) * visCount)));
        renderHeroIndexChart();
      });

      canvas.addEventListener('mouseleave', () => {
        state.heroChart.hoverIndex = -1;
        renderHeroIndexChart();
      });
    }

    // 渲染權值股貢獻排行
    function renderHeavyweightList() {
      const container = document.getElementById('heavyweightList');
      container.innerHTML = heavyweightStocksDB.map(hw => {
        const isUp = hw.change >= 0;
        const col = isUp ? 'text-red-400' : 'text-emerald-400';
        return `
          <button onclick="drillDownStock('${hw.code}')" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-[#0a0d12] hover:bg-[#192030] border border-[#262d3d]/80 transition text-left group">
            <div class="flex items-center gap-2">
              <span class="font-mono font-bold text-slate-300 group-hover:text-blue-400">${hw.code}</span>
              <span class="font-bold text-white">${hw.name}</span>
            </div>
            <div class="flex items-center gap-2.5">
              <span class="font-bold ${col}">${hw.price.toFixed(1)}</span>
              <span class="text-[11px] ${col} w-12 text-right">${isUp ? '+' : ''}${hw.changePct.toFixed(2)}%</span>
              <span class="px-1.5 py-0.2 rounded text-[11px] font-bold ${isUp ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}">
                ${isUp ? '+' : ''}${hw.contribPts.toFixed(1)}點
              </span>
            </div>
          </button>
        `;
      }).join('');
    }

    // 渲染產業族群熱力圖
    function renderSectorHeatmap() {
      const grid = document.getElementById('sectorHeatmapGrid');
      grid.innerHTML = sectorsData.map(sec => {
        const isUp = sec.changePct >= 0;
        const isSelected = state.screener.sector === sec.id;
        let bgStyle = '';
        if (sec.changePct >= 3) bgStyle = 'bg-gradient-to-br from-red-600/85 to-red-800/90 border-red-400/60';
        else if (sec.changePct >= 1.5) bgStyle = 'bg-gradient-to-br from-red-600/60 to-red-900/75 border-red-500/50';
        else if (sec.changePct >= 0) bgStyle = 'bg-gradient-to-br from-red-600/35 to-red-950/65 border-red-500/40';
        else if (sec.changePct > -1) bgStyle = 'bg-gradient-to-br from-emerald-600/35 to-emerald-950/65 border-emerald-500/40';
        else bgStyle = 'bg-gradient-to-br from-emerald-600/65 to-emerald-900/80 border-emerald-400/50';

        const ringCls = isSelected ? 'ring-2 ring-amber-400 scale-[1.02]' : 'hover:scale-[1.02]';
        return `
          <button onclick="selectSectorFilter('${sec.id}')" class="${bgStyle} ${ringCls} border rounded-xl p-3 text-left transition-all duration-200 flex flex-col justify-between min-h-[92px] shadow">
            <div class="flex items-center justify-between gap-1">
              <span class="font-bold text-xs sm:text-sm text-white truncate">${sec.name}</span>
              ${isSelected ? '<span class="w-2 h-2 rounded-full bg-amber-300 shrink-0"></span>' : ''}
            </div>
            <div class="my-1 tabular-nums">
              <div class="text-base sm:text-lg font-bold text-white">${isUp ? '+' : ''}${sec.changePct.toFixed(2)}%</div>
              <div class="text-[11px] text-white/80">資金 ${sec.flow >= 0 ? '+' : ''}${sec.flow.toFixed(1)}億</div>
            </div>
            <div class="text-[10px] text-white/75 truncate">領漲：${sec.leader}</div>
          </button>
        `;
      }).join('');

      const badge = document.getElementById('activeSectorBadge');
      if (state.screener.sector !== 'ALL') {
        badge.textContent = `已篩選族群：${state.screener.sector}`;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }

    function selectSectorFilter(sectorId) {
      state.screener.sector = (state.screener.sector === sectorId && sectorId !== 'ALL') ? 'ALL' : sectorId;
      renderSectorHeatmap();
      renderScreenerTable();
    }

    function setQuickFilter(qf) {
      state.screener.quickFilter = qf;
      document.querySelectorAll('.qf-btn').forEach(btn => {
        btn.className = btn.id === `qf_${qf}`
          ? 'qf-btn px-3 py-1.5 rounded-lg font-semibold bg-blue-600 text-white transition'
          : 'qf-btn px-3 py-1.5 rounded-lg font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition';
      });
      renderScreenerTable();
    }

    function sortScreener(key) {
      if (state.screener.sortKey === key) {
        state.screener.sortDir = state.screener.sortDir === 'desc' ? 'asc' : 'desc';
      } else {
        state.screener.sortKey = key;
        state.screener.sortDir = 'desc';
      }
      ['code', 'sector', 'capital', 'price', 'changePct', 'volume', 'volRatio', 'instStreak'].forEach(k => {
        const el = document.getElementById(`sort_${k}`);
        if (el) el.textContent = k === state.screener.sortKey ? (state.screener.sortDir === 'desc' ? '▼' : '▲') : '';
      });
      renderScreenerTable();
    }

    function buildSparklineSVG(stock) {
      const pts = stock.series.intraday.filter((_, i) => i % 4 === 0);
      const min = Math.min(...pts.map(p => p.close), stock.prevClose);
      const max = Math.max(...pts.map(p => p.close), stock.prevClose);
      const range = Math.max(0.1, max - min);
      const w = 88, h = 28;
      const coords = pts.map((p, i) => {
        const x = (i / (pts.length - 1)) * w;
        const y = h - 3 - ((p.close - min) / range) * (h - 6);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
      const prevY = (h - 3 - ((stock.prevClose - min) / range) * (h - 6)).toFixed(1);
      const stroke = stock.change >= 0 ? '#ef4444' : '#10b981';
      return `
        <svg width="${w}" height="${h}" class="inline-block overflow-visible">
          <line x1="0" y1="${prevY}" x2="${w}" y2="${prevY}" stroke="#475569" stroke-width="1" stroke-dasharray="2,2" />
          <polyline fill="none" stroke="${stroke}" stroke-width="1.6" points="${coords}" />
        </svg>
      `;
    }

    function renderScreenerTable() {
      const tbody = document.getElementById('screenerTableBody');
      let list = [...smallCapStocksDB];

      if (state.screener.sector !== 'ALL') {
        list = list.filter(s => s.sector === state.screener.sector);
      }
      const qf = state.screener.quickFilter;
      if (qf === 'CAP20') list = list.filter(s => s.capital < 20);
      else if (qf === 'CAP50') list = list.filter(s => s.capital < 50);
      else if (qf === 'VOL_SURGE') list = list.filter(s => s.volRatio >= 1.5);
      else if (qf === 'INST_STREAK') list = list.filter(s => s.instStreak >= 3);

      const { sortKey, sortDir } = state.screener;
      list.sort((a, b) => {
        const va = a[sortKey], vb = b[sortKey];
        if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
        return sortDir === 'asc' ? va - vb : vb - va;
      });

      document.getElementById('screenerCountBadge').textContent = `${list.length} 檔標的`;

      if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="py-10 text-center text-[#848e9c] text-sm">目前篩選條件下無符合標的，請切換其他篩選按鈕。</td></tr>`;
        return;
      }

      tbody.innerHTML = list.map(s => {
        const isUp = s.change > 0, isDown = s.change < 0;
        const col = isUp ? 'text-red-400' : (isDown ? 'text-emerald-400' : 'text-slate-300');
        const badgeBg = isUp ? 'bg-red-500/15 text-red-400 border-red-500/30' : (isDown ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-slate-700/40 text-slate-300 border-slate-600');

        return `
          <tr onclick="drillDownStock('${s.code}')" class="hover:bg-[#192030] cursor-pointer transition group">
            <td class="py-2.5 px-3">
              <div class="flex items-center gap-2">
                <span class="font-mono font-bold text-white group-hover:text-blue-400 transition">${s.code}</span>
                <span class="font-bold text-slate-100">${s.name}</span>
                <span class="text-[10px] px-1.5 py-0.2 rounded ${s.market === '上櫃' ? 'bg-amber-500/15 text-amber-300' : 'bg-slate-700/70 text-slate-300'}">${s.market}</span>
              </div>
            </td>
            <td class="py-2.5 px-2.5"><span class="text-xs px-2 py-0.5 rounded bg-[#0a0d12] border border-[#262d3d] text-slate-300">${s.sector}</span></td>
            <td class="py-2.5 px-2.5 text-right text-slate-300">${s.capital.toFixed(1)}</td>
            <td class="py-2.5 px-3 text-right font-bold text-sm ${col}">${s.price.toFixed(1)}</td>
            <td class="py-2.5 px-3 text-right"><span class="px-2 py-0.5 rounded border text-xs font-bold ${badgeBg}">${isUp ? '+' : ''}${s.changePct.toFixed(2)}%</span></td>
            <td class="py-2.5 px-3 text-right text-slate-200">${s.volume.toLocaleString()}</td>
            <td class="py-2.5 px-2.5 text-right font-semibold ${s.volRatio >= 1.5 ? 'text-amber-400' : 'text-slate-400'}">${s.volRatio.toFixed(2)}x</td>
            <td class="py-2.5 px-3 text-right font-semibold ${s.instStreak >= 3 ? 'text-red-400' : 'text-slate-400'}">${s.instStreak > 0 ? `連買 ${s.instStreak} 日` : '調節'}</td>
            <td class="py-2.5 px-3 text-center">${buildSparklineSVG(s)}</td>
            <td class="py-2.5 px-3 text-right">
              <button class="px-2.5 py-1 rounded-lg bg-blue-600/20 group-hover:bg-blue-600 text-blue-400 group-hover:text-white border border-blue-500/40 text-xs font-semibold transition">
                K線終端 →
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    // =========================================================================
    // 6. VIEW 2: 個股深度終端 (K 線圖、最佳五檔、Tick明細與五大分析分頁籤)
    // =========================================================================
    function getCurrentStock() {
      return allStocksDB.find(s => s.code === state.selectedStockCode) || smallCapStocksDB[0];
    }

    function drillDownStock(code) {
      state.selectedStockCode = code;
      state.view = 'stock';
      state.chart.offsetBars = 0;
      state.chart.hoverIndex = -1;

      document.getElementById('viewMarket').classList.add('hidden');
      document.getElementById('viewStock').classList.remove('hidden');
      window.scrollTo({ top: 0, behavior: 'smooth' });

      updateBreadcrumbs();
      renderStockHeader();
      renderOrderBookAndTape(true);
      renderStockMainChart();
      renderActiveDetailTab();
    }

    function renderStockHeader() {
      const s = getCurrentStock();
      const switcher = document.getElementById('stockQuickSwitcher');
      switcher.innerHTML = allStocksDB.map(item =>
        `<option value="${item.code}" ${item.code === s.code ? 'selected' : ''}>${item.code} ${item.name} (${item.sector})</option>`
      ).join('');

      document.getElementById('detailStockTitle').textContent = `${s.code} ${s.name}`;
      document.getElementById('detailMarketBadge').textContent = s.market === '上櫃' ? '上櫃 OTC' : '上市 TWSE';
      document.getElementById('detailCapitalBadge').textContent = `股本 ${s.capital.toFixed(1)} 億`;
      document.getElementById('detailSectorBadge').textContent = s.sector;
      document.getElementById('detailCompanyDesc').textContent = s.desc;

      updateStockLivePriceHeader();
    }

    function updateStockLivePriceHeader() {
      const s = getCurrentStock();
      const isUp = s.change > 0, isDown = s.change < 0;
      const col = isUp ? 'text-red-400' : (isDown ? 'text-emerald-400' : 'text-slate-200');

      const priceEl = document.getElementById('detailPrice');
      priceEl.textContent = s.price.toFixed(1);
      priceEl.className = `text-3xl sm:text-4xl font-bold ${col}`;

      const chgEl = document.getElementById('detailChange');
      chgEl.textContent = `${isUp ? '▲ +' : (isDown ? '▼ ' : '')}${s.change.toFixed(1)}`;
      chgEl.className = col;

      const pctEl = document.getElementById('detailChangePct');
      pctEl.textContent = `${isUp ? '+' : ''}${s.changePct.toFixed(2)}%`;
      pctEl.className = col;

      document.getElementById('detailOpen').textContent = s.open.toFixed(1);
      document.getElementById('detailOpen').className = `font-semibold ${s.open >= s.prevClose ? 'text-red-400' : 'text-emerald-400'}`;
      document.getElementById('detailHigh').textContent = s.high.toFixed(1);
      document.getElementById('detailLow').textContent = s.low.toFixed(1);
      document.getElementById('detailPrevClose').textContent = s.prevClose.toFixed(1);
      document.getElementById('detailAmplitude').textContent = `${(((s.high - s.low) / s.prevClose) * 100).toFixed(2)}%`;
      document.getElementById('detailTurnoverAmt').textContent = `${((s.price * s.volume * 1000) / 100000000).toFixed(2)} 億`;
    }

    function setChartTimeframe(tf) {
      state.chart.timeframe = tf;
      state.chart.offsetBars = 0;
      state.chart.hoverIndex = -1;
      document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.className = btn.id === `tf_${tf}`
          ? 'tf-btn px-2.5 py-1 text-xs rounded-md font-medium bg-blue-600 text-white transition'
          : 'tf-btn px-2.5 py-1 text-xs rounded-md font-medium text-[#848e9c] hover:text-white transition';
      });
      renderStockMainChart();
    }

    function toggleOverlay(key) {
      state.chart.overlays[key] = !state.chart.overlays[key];
      const active = state.chart.overlays[key];
      const styles = {
        MA5:  'bg-amber-500/20 text-amber-300 border-amber-500/40',
        MA10: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
        MA20: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
        MA60: 'bg-pink-500/20 text-pink-300 border-pink-500/40',
        BOLL: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40',
        VWAP: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'
      };
      const el = document.getElementById(`ov_${key}`);
      el.className = active
        ? `px-2 py-1 rounded border font-mono transition ${styles[key]}`
        : 'px-2 py-1 rounded border font-mono transition bg-[#0a0d12] text-[#848e9c] border-[#262d3d]';
      renderStockMainChart();
    }

    function setSubIndicator(ind) {
      state.chart.subIndicator = ind;
      ['VOL', 'MACD', 'KD', 'RSI'].forEach(k => {
        const el = document.getElementById(`sub_${k}`);
        el.className = k === ind
          ? 'px-2.5 py-1 rounded-md font-medium bg-blue-600 text-white transition'
          : 'px-2.5 py-1 rounded-md font-medium bg-[#0a0d12] text-[#848e9c] hover:text-white border border-[#262d3d] transition';
      });
      renderStockMainChart();
    }

    function zoomChart(factor) {
      state.chart.visibleBars = Math.max(20, Math.min(120, Math.round(state.chart.visibleBars * factor)));
      renderStockMainChart();
    }

    function resetChartZoom() {
      state.chart.visibleBars = 65;
      state.chart.offsetBars = 0;
      renderStockMainChart();
    }

    function renderStockMainChart() {
      const canvas = document.getElementById('stockMainCanvas');
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);

      const W = rect.width, H = rect.height;
      const padL = 10, padR = 62, padT = 14, padB = 24;
      const plotW = W - padL - padR;
      const plotH = H - padT - padB;
      const mainH = plotH * 0.70;
      const subTop = padT + mainH + plotH * 0.05;
      const subH = plotH * 0.25;

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#0a0d12';
      ctx.fillRect(0, 0, W, H);

      const s = getCurrentStock();
      const tf = state.chart.timeframe;
      const fullSeries = s.series[tf] || s.series['1d'];
      const isIntraday = tf === 'intraday';

      const ma5All = calcSMA(fullSeries, 5);
      const ma10All = calcSMA(fullSeries, 10);
      const ma20All = calcSMA(fullSeries, 20);
      const ma60All = calcSMA(fullSeries, 60);
      const bollAll = calcBollinger(fullSeries, 20, 2);
      const macdAll = calcMACD(fullSeries);
      const kdAll = calcKD(fullSeries);
      const rsi6All = calcRSI(fullSeries, 6);
      const rsi12All = calcRSI(fullSeries, 12);

      const total = fullSeries.length;
      const visCount = isIntraday ? total : Math.min(total, state.chart.visibleBars);
      const maxOffset = Math.max(0, total - visCount);
      state.chart.offsetBars = Math.max(0, Math.min(maxOffset, state.chart.offsetBars));
      const endIdx = total - state.chart.offsetBars;
      const startIdx = Math.max(0, endIdx - visCount);
      const slice = fullSeries.slice(startIdx, endIdx);

      let minP = Infinity, maxP = -Infinity;
      slice.forEach((c, idx) => {
        const gIdx = startIdx + idx;
        let hi = isIntraday ? Math.max(c.close, c.vwap, s.prevClose) : c.high;
        let lo = isIntraday ? Math.min(c.close, c.vwap, s.prevClose) : c.low;
        if (!isIntraday && state.chart.overlays.BOLL && bollAll[gIdx].upper !== null) {
          hi = Math.max(hi, bollAll[gIdx].upper);
          lo = Math.min(lo, bollAll[gIdx].lower);
        }
        if (hi > maxP) maxP = hi;
        if (lo < minP) minP = lo;
      });
      const pSpan = Math.max(0.5, maxP - minP);
      minP -= pSpan * 0.06;
      maxP += pSpan * 0.06;

      const yMain = (p) => padT + ((maxP - p) / (maxP - minP)) * mainH;
      const xBar = (i) => padL + ((i + 0.5) / slice.length) * plotW;
      const barW = Math.max(2, (plotW / slice.length) * 0.66);

      ctx.strokeStyle = '#1b2232';
      ctx.lineWidth = 1;
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#848e9c';
      ctx.textAlign = 'left';
      for (let g = 0; g <= 4; g++) {
        const y = padT + (g / 4) * mainH;
        const val = maxP - (g / 4) * (maxP - minP);
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(W - padR, y);
        ctx.stroke();
        ctx.fillText(val.toFixed(1), W - padR + 6, y + 3);
      }

      if (isIntraday) {
        const prevY = yMain(s.prevClose);
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = '#64748b';
        ctx.beginPath();
        ctx.moveTo(padL, prevY);
        ctx.lineTo(W - padR, prevY);
        ctx.stroke();
        ctx.restore();

        const isUp = s.price >= s.prevClose;
        const lineCol = isUp ? '#ef4444' : '#10b981';
        const grad = ctx.createLinearGradient(0, padT, 0, padT + mainH);
        grad.addColorStop(0, isUp ? 'rgba(239,68,68,0.28)' : 'rgba(16,185,129,0.28)');
        grad.addColorStop(1, 'rgba(10,13,18,0)');

        ctx.beginPath();
        slice.forEach((pt, i) => {
          const x = xBar(i), y = yMain(pt.close);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = lineCol;
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.lineTo(xBar(slice.length - 1), padT + mainH);
        ctx.lineTo(xBar(0), padT + mainH);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        slice.forEach((pt, i) => {
          const x = xBar(i), y = yMain(pt.vwap);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      } else {
        if (state.chart.overlays.BOLL) {
          ctx.fillStyle = 'rgba(99, 102, 241, 0.08)';
          ctx.beginPath();
          let first = true;
          slice.forEach((_, i) => {
            const b = bollAll[startIdx + i];
            if (b.upper === null) return;
            const x = xBar(i), y = yMain(b.upper);
            if (first) { ctx.moveTo(x, y); first = false; }
            else ctx.lineTo(x, y);
          });
          for (let i = slice.length - 1; i >= 0; i--) {
            const b = bollAll[startIdx + i];
            if (b.lower !== null) ctx.lineTo(xBar(i), yMain(b.lower));
          }
          ctx.closePath();
          ctx.fill();
        }

        slice.forEach((c, i) => {
          const x = xBar(i);
          const isUp = c.close >= c.open;
          const col = isUp ? '#ef4444' : '#10b981';
          ctx.strokeStyle = col;
          ctx.fillStyle = col;
          ctx.lineWidth = 1.2;

          ctx.beginPath();
          ctx.moveTo(x, yMain(c.high));
          ctx.lineTo(x, yMain(c.low));
          ctx.stroke();

          const topY = yMain(Math.max(c.open, c.close));
          const botY = yMain(Math.min(c.open, c.close));
          ctx.fillRect(x - barW / 2, topY, barW, Math.max(1.8, botY - topY));
        });

        [
          { key: 'MA5',  arr: ma5All,  col: '#f59e0b' },
          { key: 'MA10', arr: ma10All, col: '#c084fc' },
          { key: 'MA20', arr: ma20All, col: '#22d3ee' },
          { key: 'MA60', arr: ma60All, col: '#f472b6' }
        ].forEach(cfg => {
          if (!state.chart.overlays[cfg.key]) return;
          ctx.beginPath();
          let started = false;
          slice.forEach((_, i) => {
            const v = cfg.arr[startIdx + i];
            if (v === null) return;
            const x = xBar(i), y = yMain(v);
            if (!started) { ctx.moveTo(x, y); started = true; }
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = cfg.col;
          ctx.lineWidth = 1.4;
          ctx.stroke();
        });

        if (state.chart.overlays.VWAP) {
          let cumPV = 0, cumV = 0;
          ctx.beginPath();
          slice.forEach((c, i) => {
            cumPV += ((c.high + c.low + c.close) / 3) * c.volume;
            cumV += c.volume;
            const x = xBar(i), y = yMain(cumPV / cumV);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = '#fde047';
          ctx.lineWidth = 1.4;
          ctx.stroke();
        }
      }

      const lastY = yMain(s.price);
      ctx.fillStyle = s.change >= 0 ? '#ef4444' : '#10b981';
      ctx.fillRect(W - padR + 2, lastY - 8, padR - 4, 16);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 10px "JetBrains Mono", monospace';
      ctx.fillText(s.price.toFixed(1), W - padR + 6, lastY + 3);

      ctx.strokeStyle = '#262d3d';
      ctx.beginPath();
      ctx.moveTo(padL, subTop - 4);
      ctx.lineTo(W - padR, subTop - 4);
      ctx.stroke();

      const subInd = state.chart.subIndicator;
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#848e9c';

      if (subInd === 'VOL') {
        const maxV = Math.max(...slice.map(c => c.volume), 1);
        ctx.fillText(`${Math.round(maxV)}張`, W - padR + 6, subTop + 8);
        slice.forEach((c, i) => {
          const prev = i > 0 ? slice[i - 1].close : s.prevClose;
          const isUp = isIntraday ? c.close >= prev : c.close >= c.open;
          ctx.fillStyle = isUp ? 'rgba(239, 68, 68, 0.75)' : 'rgba(16, 185, 129, 0.75)';
          const h = (c.volume / maxV) * subH;
          ctx.fillRect(xBar(i) - barW / 2, subTop + subH - h, barW, h);
        });
      } else if (subInd === 'MACD') {
        const mSlice = macdAll.slice(startIdx, endIdx);
        const absMax = Math.max(...mSlice.map(m => Math.max(Math.abs(m.dif), Math.abs(m.dem), Math.abs(m.osc))), 0.1);
        const zeroY = subTop + subH / 2;
        ctx.fillText(`+${absMax.toFixed(1)}`, W - padR + 6, subTop + 8);
        mSlice.forEach((m, i) => {
          const h = (m.osc / absMax) * (subH / 2);
          ctx.fillStyle = m.osc >= 0 ? 'rgba(239, 68, 68, 0.75)' : 'rgba(16, 185, 129, 0.75)';
          if (h >= 0) ctx.fillRect(xBar(i) - barW / 2, zeroY - h, barW, h);
          else ctx.fillRect(xBar(i) - barW / 2, zeroY, barW, -h);
        });
        [
          { key: 'dif', col: '#f59e0b' },
          { key: 'dem', col: '#22d3ee' }
        ].forEach(l => {
          ctx.beginPath();
          mSlice.forEach((m, i) => {
            const x = xBar(i), y = zeroY - (m[l.key] / absMax) * (subH / 2);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = l.col;
          ctx.lineWidth = 1.3;
          ctx.stroke();
        });
      } else if (subInd === 'KD') {
        const kdSlice = kdAll.slice(startIdx, endIdx);
        const yKD = (v) => subTop + ((100 - v) / 100) * subH;
        ctx.fillText('80', W - padR + 6, yKD(80) + 3);
        ctx.fillText('20', W - padR + 6, yKD(20) + 3);
        [
          { key: 'k', col: '#f59e0b' },
          { key: 'd', col: '#22d3ee' }
        ].forEach(l => {
          ctx.beginPath();
          kdSlice.forEach((item, i) => {
            const x = xBar(i), y = yKD(item[l.key]);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = l.col;
          ctx.lineWidth = 1.3;
          ctx.stroke();
        });
      } else if (subInd === 'RSI') {
        const r6 = rsi6All.slice(startIdx, endIdx);
        const r12 = rsi12All.slice(startIdx, endIdx);
        const yR = (v) => subTop + ((100 - v) / 100) * subH;
        ctx.fillText('70', W - padR + 6, yR(70) + 3);
        ctx.fillText('30', W - padR + 6, yR(30) + 3);
        [
          { arr: r6, col: '#f59e0b' },
          { arr: r12, col: '#c084fc' }
        ].forEach(l => {
          ctx.beginPath();
          l.arr.forEach((val, i) => {
            const x = xBar(i), y = yR(val);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = l.col;
          ctx.lineWidth = 1.3;
          ctx.stroke();
        });
      }

      ctx.fillStyle = '#848e9c';
      ctx.textAlign = 'center';
      const step = Math.max(1, Math.floor(slice.length / 5));
      for (let i = 0; i < slice.length; i += step) {
        ctx.fillText(slice[i].label, xBar(i), H - 6);
      }

      const activeLocal = (state.chart.hoverIndex >= 0 && state.chart.hoverIndex < slice.length)
        ? state.chart.hoverIndex
        : slice.length - 1;
      const activeGlobal = startIdx + activeLocal;
      const bar = slice[activeLocal];

      if (state.chart.hoverIndex >= 0 && state.chart.hoverIndex < slice.length) {
        const cx = xBar(activeLocal), cy = yMain(bar.close);
        ctx.save();
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = '#94a3b8';
        ctx.beginPath();
        ctx.moveTo(cx, padT);
        ctx.lineTo(cx, subTop + subH);
        ctx.moveTo(padL, cy);
        ctx.lineTo(W - padR, cy);
        ctx.stroke();
        ctx.restore();
      }

      const readoutEl = document.getElementById('klineReadoutBar');
      const isBarUp = bar.close >= bar.open;
      const barCol = isBarUp ? 'text-red-400' : 'text-emerald-400';
      const m5v = ma5All[activeGlobal] ? ma5All[activeGlobal].toFixed(1) : '--';
      const m10v = ma10All[activeGlobal] ? ma10All[activeGlobal].toFixed(1) : '--';
      const m20v = ma20All[activeGlobal] ? ma20All[activeGlobal].toFixed(1) : '--';
      const kdItem = kdAll[activeGlobal];
      const macdItem = macdAll[activeGlobal];

      readoutEl.innerHTML = `
        <div class="flex flex-wrap items-center gap-2.5">
          <span class="text-white font-semibold">${bar.label}</span>
          <span>開 <b class="text-slate-200">${bar.open.toFixed(1)}</b></span>
          <span>高 <b class="text-red-400">${bar.high.toFixed(1)}</b></span>
          <span>低 <b class="text-emerald-400">${bar.low.toFixed(1)}</b></span>
          <span>收 <b class="${barCol}">${bar.close.toFixed(1)}</b></span>
          <span>量 <b class="text-amber-300">${bar.volume.toLocaleString()}張</b></span>
        </div>
        <div class="flex flex-wrap items-center gap-2.5">
          <span class="text-amber-400">MA5:${m5v}</span>
          <span class="text-purple-400">MA10:${m10v}</span>
          <span class="text-cyan-400">MA20:${m20v}</span>
          <span class="text-slate-400">K9:${kdItem.k.toFixed(1)} D9:${kdItem.d.toFixed(1)}</span>
          <span class="${macdItem.osc >= 0 ? 'text-red-400' : 'text-emerald-400'}">OSC:${macdItem.osc.toFixed(2)}</span>
        </div>
      `;
    }

    function initStockCanvasInteractions() {
      const canvas = document.getElementById('stockMainCanvas');
      canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (state.chart.timeframe === 'intraday') return;
        zoomChart(e.deltaY > 0 ? 1.15 : 0.85);
      }, { passive: false });

      canvas.addEventListener('mousedown', (e) => {
        if (state.chart.timeframe === 'intraday') return;
        state.chart.isDragging = true;
        state.chart.dragStartX = e.clientX;
        state.chart.dragStartOffset = state.chart.offsetBars;
        canvas.classList.add('grabbing');
      });

      window.addEventListener('mouseup', () => {
        state.chart.isDragging = false;
        canvas.classList.remove('grabbing');
      });

      canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const plotW = rect.width - 72;
        const s = getCurrentStock();
        const fullLen = (s.series[state.chart.timeframe] || s.series['1d']).length;
        const visCount = state.chart.timeframe === 'intraday' ? fullLen : Math.min(fullLen, state.chart.visibleBars);

        if (state.chart.isDragging) {
          const dx = e.clientX - state.chart.dragStartX;
          const barDelta = Math.round((dx / plotW) * visCount);
          state.chart.offsetBars = Math.max(0, Math.min(fullLen - visCount, state.chart.dragStartOffset + barDelta));
          renderStockMainChart();
          return;
        }
        const x = e.clientX - rect.left - 10;
        state.chart.hoverIndex = Math.max(0, Math.min(visCount - 1, Math.floor((x / plotW) * visCount)));
        renderStockMainChart();
      });

      canvas.addEventListener('mouseleave', () => {
        state.chart.hoverIndex = -1;
        renderStockMainChart();
      });
    }

    function getTaiwanTickStep(price) {
      if (price < 10) return 0.01;
      if (price < 50) return 0.05;
      if (price < 100) return 0.1;
      if (price < 500) return 0.5;
      if (price < 1000) return 1.0;
      return 5.0;
    }

    function renderOrderBookAndTape(resetTape = false) {
      const s = getCurrentStock();
      const step = getTaiwanTickStep(s.price);
      document.getElementById('orderBookSpread').textContent = `檔位: ${step}`;

      const outerPct = Math.min(78, Math.max(28, 50 + s.changePct * 2.4 + (Math.random() - 0.5) * 3));
      const innerPct = 100 - outerPct;
      document.getElementById('outerRatioText').textContent = `${outerPct.toFixed(1)}%`;
      document.getElementById('innerRatioText').textContent = `${innerPct.toFixed(1)}%`;
      document.getElementById('outerRatioBar').style.width = `${outerPct.toFixed(1)}%`;
      document.getElementById('innerRatioBar').style.width = `${innerPct.toFixed(1)}%`;

      const asks = [], bids = [];
      for (let i = 5; i >= 1; i--) {
        asks.push({ label: `賣${i}`, price: Number((s.price + step * i).toFixed(2)), lots: Math.max(2, Math.round((15 + Math.random() * 85) * (s.volume / 6000))) });
      }
      for (let i = 1; i <= 5; i++) {
        bids.push({ label: `買${i}`, price: Number((s.price - step * (i - 1)).toFixed(2)), lots: Math.max(3, Math.round((18 + Math.random() * 95) * (s.volume / 6000))) });
      }
      const maxLots = Math.max(...asks.map(a => a.lots), ...bids.map(b => b.lots), 1);

      document.getElementById('askLevelsContainer').innerHTML = asks.map(a => `
        <div class="relative flex items-center justify-between px-2 py-1 rounded overflow-hidden">
          <div class="absolute right-0 top-0 bottom-0 bg-emerald-500/15" style="width: ${Math.round((a.lots / maxLots) * 100)}%"></div>
          <span class="relative text-[#848e9c] w-8">${a.label}</span>
          <span class="relative font-semibold text-emerald-400">${a.price.toFixed(1)}</span>
          <span class="relative text-slate-200 font-medium">${a.lots}</span>
        </div>
      `).join('');

      document.getElementById('bidLevelsContainer').innerHTML = bids.map(b => `
        <div class="relative flex items-center justify-between px-2 py-1 rounded overflow-hidden">
          <div class="absolute right-0 top-0 bottom-0 bg-red-500/15" style="width: ${Math.round((b.lots / maxLots) * 100)}%"></div>
          <span class="relative text-[#848e9c] w-8">${b.label}</span>
          <span class="relative font-semibold text-red-400">${b.price.toFixed(1)}</span>
          <span class="relative text-slate-200 font-medium">${b.lots}</span>
        </div>
      `).join('');

      const lastP = document.getElementById('bookLastPrice');
      lastP.textContent = s.price.toFixed(1);
      lastP.className = `font-bold text-base ${s.change >= 0 ? 'text-red-400' : 'text-emerald-400'}`;

      const tapeEl = document.getElementById('tickTapeContainer');
      if (resetTape) {
        const now = new Date();
        const rows = [];
        for (let i = 0; i < 14; i++) {
          const t = new Date(now.getTime() - i * 4000);
          const timeStr = `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}:${String(t.getSeconds()).padStart(2, '0')}`;
          const isOuter = Math.random() > 0.42;
          const p = isOuter ? s.price : Number((s.price - step).toFixed(1));
          rows.push(buildTickRowHTML(timeStr, p, Math.max(1, Math.round(1 + Math.random() * 24)), isOuter));
        }
        tapeEl.innerHTML = rows.join('');
      }
    }

    function buildTickRowHTML(timeStr, price, lots, isOuter) {
      const col = isOuter ? 'text-red-400' : 'text-emerald-400';
      const tag = isOuter
        ? '<span class="px-1 rounded bg-red-500/20 text-red-400 text-[10px]">外</span>'
        : '<span class="px-1 rounded bg-emerald-500/20 text-emerald-400 text-[10px]">內</span>';
      return `
        <div class="flex items-center justify-between px-2 py-0.5 rounded bg-[#0a0d12]/60 hover:bg-[#192030]">
          <span class="text-[#848e9c]">${timeStr}</span>
          <span class="font-semibold ${col}">${price.toFixed(1)}</span>
          <div class="flex items-center gap-1.5">
            <span class="text-white font-medium">${lots}</span>
            ${tag}
          </div>
        </div>
      `;
    }

    // =========================================================================
    // 7. 底部五大細分功能分頁籤
    // =========================================================================
    function setDetailTab(tabKey) {
      state.detailTab = tabKey;
      ['tech', 'chips', 'fund', 'peers', 'alerts'].forEach(k => {
        const btn = document.getElementById(`tabBtn_${k}`);
        const panel = document.getElementById(`tabPanel_${k}`);
        if (k === tabKey) {
          btn.className = 'detail-tab-btn px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-lg border-t border-x border-[#262d3d] bg-[#121722] text-blue-400 whitespace-nowrap transition';
          panel.classList.remove('hidden');
        } else {
          btn.className = 'detail-tab-btn px-4 py-2.5 text-xs sm:text-sm font-semibold rounded-t-lg border-t border-x border-transparent text-[#848e9c] hover:text-white whitespace-nowrap transition';
          panel.classList.add('hidden');
        }
      });
      renderActiveDetailTab();
    }

    function renderActiveDetailTab() {
      const tab = state.detailTab;
      if (tab === 'tech') renderTechAnalysisTab();
      else if (tab === 'chips') renderChipsAnalysisTab();
      else if (tab === 'fund') renderFundAnalysisTab();
      else if (tab === 'peers') renderPeersTab();
      else if (tab === 'alerts') renderAlertsAndNotesTab();
    }

    function renderTechAnalysisTab() {
      const s = getCurrentStock();
      const isBull = s.changePct >= 0;
      const tfs = [
        { label: '1分K 短線', state: isBull ? '強勢多頭' : '偏空整理', up: isBull },
        { label: '5分K 波段', state: isBull ? '多頭攻擊' : '回測支撐', up: isBull },
        { label: '15分K 趨勢', state: isBull ? '均線發散' : '區間震盪', up: isBull },
        { label: '60分K 中線', state: s.instStreak >= 3 ? '多頭排列' : '中性整理', up: s.instStreak >= 3 },
        { label: '日K 主趨勢', state: s.instStreak >= 2 ? '強勢多頭' : '高檔震盪', up: s.instStreak >= 2 },
        { label: '週K 長波段', state: s.revYoY > 15 ? '長多格局' : '築底轉強', up: true }
      ];
      const pct = Math.round((tfs.filter(t => t.up).length / tfs.length) * 100);
      document.getElementById('resonanceBadge').textContent = `共振度 ${pct}% ${pct >= 65 ? '多方主導' : '多空拉鋸'}`;

      document.getElementById('mtfMatrixGrid').innerHTML = tfs.map(t => `
        <div class="p-2.5 rounded-lg bg-[#121722] border border-[#262d3d] flex flex-col justify-between">
          <span class="text-[#848e9c] text-[11px]">${t.label}</span>
          <span class="font-bold mt-1 ${t.up ? 'text-red-400' : 'text-emerald-400'}">● ${t.state}</span>
        </div>
      `).join('');

      const daily = s.series['1d'];
      const ma5 = calcSMA(daily, 5).slice(-1)[0] || s.price;
      const ma20 = calcSMA(daily, 20).slice(-1)[0] || s.price;
      const kd = calcKD(daily).slice(-1)[0];
      const macd = calcMACD(daily).slice(-1)[0];
      const rsi6 = calcRSI(daily, 6).slice(-1)[0];

      document.getElementById('techDiagnosisList').innerHTML = `
        <div class="flex items-center justify-between p-2 rounded bg-[#121722] border border-[#262d3d]">
          <span class="text-[#848e9c]">均線結構 (5MA / 20MA)</span>
          <span class="font-semibold ${s.price >= ma5 ? 'text-red-400' : 'text-emerald-400'}">${s.price >= ma5 ? '站穩 5MA 之上' : '回測月線'} (${ma5.toFixed(1)} / ${ma20.toFixed(1)})</span>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#121722] border border-[#262d3d]">
          <span class="text-[#848e9c]">KD 隨機指標 (9,3,3)</span>
          <span class="font-semibold ${kd.k >= kd.d ? 'text-red-400' : 'text-emerald-400'}">K(${kd.k.toFixed(1)}) ${kd.k >= kd.d ? '黃金交叉' : '高檔整理'} D(${kd.d.toFixed(1)})</span>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#121722] border border-[#262d3d]">
          <span class="text-[#848e9c]">MACD 動能柱狀體</span>
          <span class="font-semibold ${macd.osc >= 0 ? 'text-red-400' : 'text-emerald-400'}">${macd.osc >= 0 ? '紅柱多方動能' : '綠柱收斂'} (OSC ${macd.osc.toFixed(2)})</span>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#121722] border border-[#262d3d]">
          <span class="text-[#848e9c]">RSI(6) 相對強弱指標</span>
          <span class="font-semibold ${rsi6 >= 50 ? 'text-amber-400' : 'text-slate-300'}">${rsi6.toFixed(1)} (${rsi6 >= 75 ? '強勢超買區' : '多頭強勢區'})</span>
        </div>
      `;

      const pivot = (s.high + s.low + s.price) / 3;
      const levels = [
        { name: '壓力二 (R2 強壓區)', val: pivot + (s.high - s.low), cls: 'text-red-400' },
        { name: '壓力一 (R1 短線壓力)', val: 2 * pivot - s.low, cls: 'text-red-300' },
        { name: '多空軸心點 (Pivot)', val: pivot, cls: 'text-amber-400' },
        { name: '支撐一 (S1 短線防守)', val: 2 * pivot - s.high, cls: 'text-emerald-300' },
        { name: '支撐二 (S2 波段強撐)', val: pivot - (s.high - s.low), cls: 'text-emerald-400' }
      ];
      document.getElementById('pivotLevelsList').innerHTML = levels.map(lv => `
        <div class="flex items-center justify-between px-2.5 py-1.5 rounded bg-[#121722] border border-[#262d3d]">
          <span class="text-[#848e9c]">${lv.name}</span>
          <span class="font-bold ${lv.cls}">${lv.val.toFixed(1)}</span>
        </div>
      `).join('');
    }

    function renderChipsAnalysisTab() {
      const s = getCurrentStock();
      const inst5d = s.instHistory.slice(-5).reduce((acc, d) => acc + d.foreign + d.trust + d.dealer, 0);
      document.getElementById('chipSummaryCards').innerHTML = `
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">外資持股比例</div><div class="text-lg font-bold text-blue-400 mt-0.5">${s.foreignHold.toFixed(1)}%</div></div>
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">投信持股比例</div><div class="text-lg font-bold text-red-400 mt-0.5">${s.instHold.toFixed(1)}%</div></div>
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">三大法人近5日累計</div><div class="text-lg font-bold ${inst5d >= 0 ? 'text-red-400' : 'text-emerald-400'} mt-0.5">${inst5d >= 0 ? '+' : ''}${inst5d.toLocaleString()} 張</div></div>
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">法人連續買超天數</div><div class="text-lg font-bold text-amber-400 mt-0.5">${s.instStreak > 0 ? `連買 ${s.instStreak} 日` : '短線調節'}</div></div>
      `;

      document.getElementById('topBuyBrokers').innerHTML = s.buyBrokers.map(b => `
        <div class="flex items-center justify-between px-2 py-1 rounded bg-[#121722]">
          <span class="text-slate-200 truncate">${b.name}</span>
          <span class="text-red-400 font-semibold">+${b.lots} <span class="text-[#848e9c] font-normal">(${b.avgPrice})</span></span>
        </div>
      `).join('');

      document.getElementById('topSellBrokers').innerHTML = s.sellBrokers.map(b => `
        <div class="flex items-center justify-between px-2 py-1 rounded bg-[#121722]">
          <span class="text-slate-200 truncate">${b.name}</span>
          <span class="text-emerald-400 font-semibold">-${b.lots} <span class="text-[#848e9c] font-normal">(${b.avgPrice})</span></span>
        </div>
      `).join('');

      document.getElementById('marginDayTradeGauges').innerHTML = `
        <div>
          <div class="flex justify-between mb-1"><span class="text-[#848e9c]">融資使用率</span><span class="font-bold text-amber-400">${s.marginUsage.toFixed(1)}%</span></div>
          <div class="w-full h-2 rounded-full bg-[#121722] overflow-hidden"><div class="h-full bg-amber-400 rounded-full" style="width: ${s.marginUsage}%"></div></div>
        </div>
        <div>
          <div class="flex justify-between mb-1"><span class="text-[#848e9c]">現股當沖比率</span><span class="font-bold text-blue-400">${s.dayTradePct.toFixed(1)}%</span></div>
          <div class="w-full h-2 rounded-full bg-[#121722] overflow-hidden"><div class="h-full bg-blue-500 rounded-full" style="width: ${s.dayTradePct}%"></div></div>
        </div>
      `;
      renderInstChipsCanvas(-1);
    }

    function renderInstChipsCanvas(hoverIdx) {
      const canvas = document.getElementById('instChipsCanvas');
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);

      const W = rect.width, H = rect.height;
      const padL = 46, padR = 12, padT = 12, padB = 22;
      const plotW = W - padL - padR, plotH = H - padT - padB;
      ctx.clearRect(0, 0, W, H);

      const s = getCurrentStock();
      const hist = s.instHistory;
      let absMax = 100;
      hist.forEach(d => absMax = Math.max(absMax, Math.abs(d.foreign), Math.abs(d.trust), Math.abs(d.dealer)));
      const zeroY = padT + plotH / 2;

      ctx.strokeStyle = '#262d3d';
      ctx.beginPath(); ctx.moveTo(padL, zeroY); ctx.lineTo(W - padR, zeroY); ctx.stroke();

      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#848e9c'; ctx.textAlign = 'right';
      ctx.fillText(`+${Math.round(absMax)}`, padL - 6, padT + 8);
      ctx.fillText('0', padL - 6, zeroY + 3);
      ctx.fillText(`-${Math.round(absMax)}`, padL - 6, padT + plotH);

      const groupW = plotW / hist.length;
      const subBarW = Math.max(2.5, groupW * 0.22);

      hist.forEach((d, i) => {
        const cx = padL + (i + 0.5) * groupW;
        if (i === hoverIdx) {
          ctx.fillStyle = 'rgba(59, 130, 246, 0.14)';
          ctx.fillRect(cx - groupW / 2, padT, groupW, plotH);
        }
        [
          { v: d.foreign, col: '#3b82f6', offset: -subBarW * 1.15 },
          { v: d.trust,   col: '#ef4444', offset: 0 },
          { v: d.dealer,  col: '#f59e0b', offset: subBarW * 1.15 }
        ].forEach(item => {
          const h = (item.v / absMax) * (plotH / 2);
          ctx.fillStyle = item.col;
          if (h >= 0) ctx.fillRect(cx + item.offset - subBarW / 2, zeroY - h, subBarW, h);
          else ctx.fillRect(cx + item.offset - subBarW / 2, zeroY, subBarW, -h);
        });
        if (i % 2 === 0 || i === hist.length - 1) {
          ctx.fillStyle = '#848e9c'; ctx.textAlign = 'center';
          ctx.fillText(d.date, cx, H - 6);
        }
      });

      const tip = document.getElementById('instChartTooltip');
      if (hoverIdx >= 0 && hoverIdx < hist.length) {
        const d = hist[hoverIdx];
        const sum = d.foreign + d.trust + d.dealer;
        tip.innerHTML = `日期 <b class="text-white">${d.date}</b> ・ 外資 <b class="text-blue-400">${d.foreign >= 0 ? '+' : ''}${d.foreign}</b> ・ 投信 <b class="text-red-400">${d.trust >= 0 ? '+' : ''}${d.trust}</b> ・ 自營 <b class="text-amber-400">${d.dealer >= 0 ? '+' : ''}${d.dealer}</b> ・ 合計 <b class="${sum >= 0 ? 'text-red-400' : 'text-emerald-400'}">${sum >= 0 ? '+' : ''}${sum}張</b>`;
      } else {
        tip.textContent = '移動滑鼠檢視每日法人買賣超明細';
      }
    }

    function renderFundAnalysisTab() {
      const s = getCurrentStock();
      document.getElementById('fundKpiCards').innerHTML = `
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">近四季累計 EPS</div><div class="text-lg font-bold text-white mt-0.5">${s.eps4Q.toFixed(2)} 元</div></div>
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">單季毛利率</div><div class="text-lg font-bold text-red-400 mt-0.5">${s.grossMargin.toFixed(1)}%</div></div>
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">營業利益率</div><div class="text-lg font-bold text-amber-400 mt-0.5">${s.opMargin.toFixed(1)}%</div></div>
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">股東權益報酬率 ROE</div><div class="text-lg font-bold text-blue-400 mt-0.5">${s.roe.toFixed(1)}%</div></div>
        <div class="bg-[#0a0d12] border border-[#262d3d] rounded-xl p-3"><div class="text-[#848e9c]">現金殖利率</div><div class="text-lg font-bold text-emerald-400 mt-0.5">${s.divYield.toFixed(2)}%</div></div>
      `;

      const [pLow, pFairLow, pFairHigh, pHigh] = s.peRange;
      const pctPos = Math.min(96, Math.max(4, ((s.pe - pLow) / (pHigh - pLow)) * 100));
      let statusLabel = '合理區間', statusCls = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      if (s.pe <= pFairLow) { statusLabel = '歷史便宜區'; statusCls = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; }
      else if (s.pe >= pFairHigh) { statusLabel = '成長溢價區'; statusCls = 'bg-red-500/20 text-red-300 border-red-500/40'; }

      document.getElementById('peBandVisual').innerHTML = `
        <div class="flex items-center justify-between">
          <div><span class="text-xs text-[#848e9c] block">目前本益比 (PE)</span><span class="text-2xl font-bold text-white tabular-nums">${s.pe.toFixed(1)}x</span></div>
          <span class="px-3 py-1 rounded-full text-xs font-bold border ${statusCls}">${statusLabel}</span>
        </div>
        <div class="relative pt-5 pb-2">
          <div class="h-3 w-full rounded-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500"></div>
          <div class="absolute top-0 -translate-x-1/2 flex flex-col items-center" style="left: ${pctPos}%">
            <span class="text-[10px] font-mono font-bold text-white bg-blue-600 px-1.5 py-0.2 rounded">${s.pe.toFixed(1)}x</span>
            <div class="w-0.5 h-4 bg-white"></div>
          </div>
          <div class="flex justify-between text-[10px] font-mono text-[#848e9c] mt-1.5">
            <span>低估 ${pLow}x</span><span>合理 ${pFairLow}x~${pFairHigh}x</span><span>高估 ${pHigh}x</span>
          </div>
        </div>
      `;
      document.getElementById('fundHighlightNote').innerHTML = `<b class="text-blue-400">機構研究摘要：</b>${s.note}`;
      renderRevenueCanvas(-1);
    }

    function renderRevenueCanvas(hoverIdx) {
      const canvas = document.getElementById('revenueCanvas');
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);

      const W = rect.width, H = rect.height;
      const padL = 44, padR = 44, padT = 14, padB = 22;
      const plotW = W - padL - padR, plotH = H - padT - padB;
      ctx.clearRect(0, 0, W, H);

      const s = getCurrentStock();
      const hist = s.revenueHistory;
      const maxRev = Math.max(...hist.map(d => d.rev)) * 1.15;
      const minYoY = Math.min(...hist.map(d => d.yoy), 0) - 10;
      const maxYoY = Math.max(...hist.map(d => d.yoy), 20) + 10;

      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#848e9c'; ctx.textAlign = 'right';
      ctx.fillText(`${maxRev.toFixed(0)}億`, padL - 6, padT + 8);
      ctx.fillText('0億', padL - 6, padT + plotH);

      ctx.textAlign = 'left'; ctx.fillStyle = '#f59e0b';
      ctx.fillText(`${maxYoY.toFixed(0)}%`, W - padR + 6, padT + 8);
      ctx.fillText(`${minYoY.toFixed(0)}%`, W - padR + 6, padT + plotH);

      const stepW = plotW / hist.length;
      const barW = Math.max(8, stepW * 0.48);

      hist.forEach((d, i) => {
        const cx = padL + (i + 0.5) * stepW;
        if (i === hoverIdx) {
          ctx.fillStyle = 'rgba(255,255,255,0.06)';
          ctx.fillRect(cx - stepW / 2, padT, stepW, plotH);
        }
        const h = (d.rev / maxRev) * plotH;
        ctx.fillStyle = 'rgba(59, 130, 246, 0.72)';
        ctx.fillRect(cx - barW / 2, padT + plotH - h, barW, h);
        ctx.fillStyle = '#848e9c'; ctx.textAlign = 'center';
        ctx.fillText(d.ym, cx, H - 6);
      });

      ctx.beginPath();
      hist.forEach((d, i) => {
        const cx = padL + (i + 0.5) * stepW;
        const y = padT + ((maxYoY - d.yoy) / Math.max(1, maxYoY - minYoY)) * plotH;
        if (i === 0) ctx.moveTo(cx, y);
        else ctx.lineTo(cx, y);
      });
      ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 2; ctx.stroke();

      hist.forEach((d, i) => {
        const cx = padL + (i + 0.5) * stepW;
        const y = padT + ((maxYoY - d.yoy) / Math.max(1, maxYoY - minYoY)) * plotH;
        ctx.fillStyle = '#f59e0b';
        ctx.beginPath(); ctx.arc(cx, y, 3, 0, Math.PI * 2); ctx.fill();
      });

      const tip = document.getElementById('revChartTooltip');
      if (hoverIdx >= 0 && hoverIdx < hist.length) {
        const d = hist[hoverIdx];
        tip.innerHTML = `月份 <b class="text-white">${d.ym}</b> ・ 合併營收 <b class="text-blue-400">${d.rev.toFixed(2)} 億元</b> ・ 年增率 YoY <b class="${d.yoy >= 0 ? 'text-red-400' : 'text-emerald-400'}">${d.yoy >= 0 ? '+' : ''}${d.yoy.toFixed(1)}%</b>`;
      } else {
        tip.textContent = '移動滑鼠檢視單月營收與年增率';
      }
    }

    function initSubTabCanvasHover() {
      const chipsCanvas = document.getElementById('instChipsCanvas');
      chipsCanvas.addEventListener('mousemove', (e) => {
        const rect = chipsCanvas.getBoundingClientRect();
        const idx = Math.floor(((e.clientX - rect.left - 46) / (rect.width - 58)) * 15);
        renderInstChipsCanvas(Math.max(0, Math.min(14, idx)));
      });
      chipsCanvas.addEventListener('mouseleave', () => renderInstChipsCanvas(-1));

      const revCanvas = document.getElementById('revenueCanvas');
      revCanvas.addEventListener('mousemove', (e) => {
        const rect = revCanvas.getBoundingClientRect();
        const idx = Math.floor(((e.clientX - rect.left - 44) / (rect.width - 88)) * 12);
        renderRevenueCanvas(Math.max(0, Math.min(11, idx)));
      });
      revCanvas.addEventListener('mouseleave', () => renderRevenueCanvas(-1));
    }

    function renderPeersTab() {
      const s = getCurrentStock();
      document.getElementById('peersSectionTitle').textContent = `【${s.sector}】同業族群橫向比較表`;
      const peers = allStocksDB.filter(item => item.sector === s.sector);

      document.getElementById('peersTableBody').innerHTML = peers.map(p => {
        const isCurrent = p.code === s.code;
        const isUp = p.change >= 0;
        const col = isUp ? 'text-red-400' : 'text-emerald-400';
        return `
          <tr class="${isCurrent ? 'bg-blue-600/15' : 'hover:bg-[#192030]'} transition">
            <td class="py-2.5 px-3 font-bold text-white">${p.code} ${p.name} ${isCurrent ? '<span class="ml-1.5 text-[10px] px-1.5 py-0.2 rounded bg-blue-500 text-white">目前標的</span>' : ''}</td>
            <td class="py-2.5 px-3 text-right text-slate-300">${p.capital.toFixed(1)}</td>
            <td class="py-2.5 px-3 text-right font-bold ${col}">${p.price.toFixed(1)}</td>
            <td class="py-2.5 px-3 text-right font-semibold ${col}">${isUp ? '+' : ''}${p.changePct.toFixed(2)}%</td>
            <td class="py-2.5 px-3 text-right text-slate-200">${p.pe.toFixed(1)}x</td>
            <td class="py-2.5 px-3 text-right text-amber-300">${p.grossMargin.toFixed(1)}%</td>
            <td class="py-2.5 px-3 text-right ${p.instStreak >= 3 ? 'text-red-400 font-semibold' : 'text-slate-400'}">${p.instStreak > 0 ? `連買 ${p.instStreak} 日` : '調節'}</td>
            <td class="py-2.5 px-3 text-right">
              ${isCurrent ? '<span class="text-xs text-[#848e9c]">檢視中</span>' : `<button onclick="drillDownStock('${p.code}')" class="px-2.5 py-1 rounded bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white border border-blue-500/40 text-xs font-semibold transition">切換分析 →</button>`}
            </td>
          </tr>
        `;
      }).join('');
    }

    function renderAlertsAndNotesTab() {
      const s = getCurrentStock();
      document.getElementById('tradeNoteTitle').textContent = `${s.code} ${s.name}・個人操盤筆記`;
      document.getElementById('tradeNoteTextarea').value = state.notes[s.code] || '';
      document.getElementById('noteSavedStatus').textContent = '';

      const listEl = document.getElementById('activeAlertsList');
      if (state.alerts.length === 0) {
        listEl.innerHTML = `<div class="text-xs text-[#848e9c] py-3 text-center">尚未設定任何觸價警示</div>`;
        return;
      }
      const labels = { PRICE_ABOVE: '現價突破 ≥', PRICE_BELOW: '現價跌破 ≤', PCT_ABOVE: '漲幅超過 ≥' };
      listEl.innerHTML = state.alerts.map(a => `
        <div class="flex items-center justify-between px-3 py-2 rounded-lg bg-[#121722] border ${a.triggered ? 'border-amber-500/60 bg-amber-500/10' : 'border-[#262d3d]'} text-xs tabular-nums">
          <div>
            <span class="font-bold text-white">${a.code} ${a.name}</span>
            <span class="text-[#848e9c] ml-2">${labels[a.type]} <b class="text-amber-300">${a.target}${a.type === 'PCT_ABOVE' ? '%' : ' 元'}</b></span>
            ${a.triggered ? '<span class="ml-2 px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 text-[10px]">已觸發</span>' : ''}
          </div>
          <button onclick="removeAlert(${a.id})" class="text-[#848e9c] hover:text-red-400 transition px-1.5">刪除</button>
        </div>
      `).join('');
    }

    function addCustomAlert() {
      const s = getCurrentStock();
      const type = document.getElementById('alertConditionType').value;
      const val = parseFloat(document.getElementById('alertTargetValue').value);
      if (isNaN(val) || val <= 0) {
        showToast('請輸入有效的目標價位或漲跌幅數值', 'info');
        return;
      }
      state.alerts.unshift({ id: Date.now(), code: s.code, name: s.name, type, target: val, triggered: false });
      document.getElementById('alertTargetValue').value = '';
      renderAlertsAndNotesTab();
      showToast(`已新增 ${s.code} ${s.name} 觸價警示`, 'info');
    }

    function removeAlert(id) {
      state.alerts = state.alerts.filter(a => a.id !== id);
      renderAlertsAndNotesTab();
    }

    function saveTradeNote() {
      const s = getCurrentStock();
      state.notes[s.code] = document.getElementById('tradeNoteTextarea').value;
      document.getElementById('noteSavedStatus').textContent = '✓ 已儲存';
      showToast(`已儲存 ${s.code} ${s.name} 個人操盤筆記`, 'info');
    }

    function showToast(message, type = 'info') {
      const container = document.getElementById('toastContainer');
      const el = document.createElement('div');
      const borderCol = type === 'alert' ? 'border-amber-500 bg-[#192030]' : 'border-blue-500/60 bg-[#121722]';
      el.className = `pointer-events-auto px-3.5 py-2.5 rounded-xl border ${borderCol} shadow-2xl text-xs text-white flex items-center gap-2 transition-all duration-300`;
      el.innerHTML = `<span class="w-2 h-2 rounded-full ${type === 'alert' ? 'bg-amber-400 animate-ping' : 'bg-blue-400'} shrink-0"></span><span>${message}</span>`;
      container.appendChild(el);
      setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3800);
    }

    // =========================================================================
    // 8. 全域即時報價模擬引擎 (大盤指數 + 權值股 + 中小型股 + 五檔明細連動)
    // =========================================================================
    let simTimer = null;

    function toggleSimulation() {
      state.simRunning = !state.simRunning;
      const btn = document.getElementById('simToggleBtn');
      const dot = document.getElementById('simStatusDot');
      const lbl = document.getElementById('simStatusLabel');
      if (state.simRunning) {
        btn.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition bg-emerald-500/20 text-emerald-300 border border-emerald-500/40';
        dot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-ping';
        lbl.textContent = '即時模擬: 開';
        startSimLoop();
      } else {
        btn.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition bg-[#0a0d12] text-[#848e9c] border border-[#262d3d]';
        dot.className = 'w-2 h-2 rounded-full bg-slate-500';
        lbl.textContent = '即時模擬: 關';
        if (simTimer) clearInterval(simTimer);
      }
    }

    function setSimSpeed(spd) {
      state.simSpeed = spd;
      document.getElementById('simSpeed1x').className = spd === 1
        ? 'px-2 py-1 text-[11px] font-mono rounded-md bg-blue-600 text-white ml-1 transition'
        : 'px-2 py-1 text-[11px] font-mono rounded-md text-[#848e9c] hover:text-white ml-1 transition';
      document.getElementById('simSpeed3x').className = spd === 3
        ? 'px-2 py-1 text-[11px] font-mono rounded-md bg-blue-600 text-white transition'
        : 'px-2 py-1 text-[11px] font-mono rounded-md text-[#848e9c] hover:text-white transition';
      if (state.simRunning) startSimLoop();
    }

    function startSimLoop() {
      if (simTimer) clearInterval(simTimer);
      simTimer = setInterval(executeMarketTick, state.simSpeed === 3 ? 650 : 1600);
    }

    function triggerFlash(elementId, isUp) {
      const el = document.getElementById(elementId);
      if (!el) return;
      el.classList.remove('flash-up', 'flash-down');
      void el.offsetWidth;
      el.classList.add(isUp ? 'flash-up' : 'flash-down');
    }

    function executeMarketTick() {
      // 1) 更新台灣加權指數 (TAIEX) 與櫃買指數 (OTC)
      ['TAIEX', 'OTC'].forEach(k => {
        const idx = macroIndices[k];
        const delta = (Math.random() - 0.48) * idx.prevClose * 0.00055;
        idx.price = Number((idx.price + delta).toFixed(2));
        if (idx.price > idx.high) idx.high = idx.price;
        if (idx.price < idx.low) idx.low = idx.price;
        idx.turnover = Number((idx.turnover + Math.random() * 1.8).toFixed(1));

        Object.keys(idx.series).forEach(tfKey => {
          const arr = idx.series[tfKey];
          const last = arr[arr.length - 1];
          if (last) {
            last.close = idx.price;
            last.high = Math.max(last.high, idx.price);
            last.low = Math.min(last.low, idx.price);
          }
        });
        if (k === state.heroIndexKey && state.view === 'market') {
          triggerFlash('heroIndexPriceBox', delta >= 0);
        }
      });

      // 2) 更新部分權值股與中小型股報價
      const activeStock = getCurrentStock();
      const targets = new Set([activeStock, heavyweightStocksDB[0]]);
      for (let i = 0; i < 4; i++) {
        targets.add(allStocksDB[Math.floor(Math.random() * allStocksDB.length)]);
      }

      targets.forEach(s => {
        const step = getTaiwanTickStep(s.price);
        const dir = Math.random() > 0.47 ? 1 : -1;
        const nextPrice = Number((s.price + dir * step).toFixed(2));
        if (nextPrice <= s.prevClose * 1.098 && nextPrice >= s.prevClose * 0.902) {
          s.price = nextPrice;
          s.change = Number((s.price - s.prevClose).toFixed(2));
          s.changePct = Number(((s.change / s.prevClose) * 100).toFixed(2));
          if (s.price > s.high) s.high = s.price;
          if (s.price < s.low) s.low = s.price;
          const addLots = Math.max(1, Math.round(1 + Math.random() * 15));
          s.volume += addLots;
          if (s.isHeavyweight) {
            s.contribPts = Number((s.changePct * (s.code === '2330' ? 86 : 12)).toFixed(1));
          }

          Object.keys(s.series).forEach(tfKey => {
            const arr = s.series[tfKey];
            const lastBar = arr[arr.length - 1];
            if (lastBar) {
              lastBar.close = s.price;
              lastBar.high = Math.max(lastBar.high, s.price);
              lastBar.low = Math.min(lastBar.low, s.price);
              lastBar.volume += addLots;
            }
          });

          // 檢查觸價預警
          state.alerts.forEach(a => {
            if (a.code === s.code && !a.triggered) {
              const hit = (a.type === 'PRICE_ABOVE' && s.price >= a.target) ||
                          (a.type === 'PRICE_BELOW' && s.price <= a.target) ||
                          (a.type === 'PCT_ABOVE' && s.changePct >= a.target);
              if (hit) {
                a.triggered = true;
                showToast(`🔔 觸價警示：${s.code} ${s.name} 現價 ${s.price.toFixed(1)} (${s.changePct >= 0 ? '+' : ''}${s.changePct.toFixed(2)}%)`, 'alert');
                if (state.view === 'stock' && state.detailTab === 'alerts') renderAlertsAndNotesTab();
              }
            }
          });
        }
      });

      // 3) 依當前視圖更新畫面
      if (state.view === 'market') {
        updateHeroIndexHeader();
        renderHeroIndexChart();
        renderHeavyweightList();
        renderScreenerTable();
      } else {
        updateStockLivePriceHeader();
        triggerFlash('detailPriceBox', activeStock.change >= 0);
        renderOrderBookAndTape(false);
        renderStockMainChart();

        const now = new Date();
        const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
        const lots = Math.max(1, Math.round(1 + Math.random() * 20));
        const isOuter = Math.random() > 0.44;
        document.getElementById('bookLastVol').textContent = `單量 ${lots} 張`;
        const tapeEl = document.getElementById('tickTapeContainer');
        if (tapeEl) {
          tapeEl.insertAdjacentHTML('afterbegin', buildTickRowHTML(timeStr, activeStock.price, lots, isOuter));
          if (tapeEl.children.length > 25) tapeEl.lastElementChild.remove();
        }
      }
    }

    // =========================================================================
    // 9. 初始化啟動與視窗縮放重繪
    // =========================================================================
    window.addEventListener('resize', () => {
      if (state.view === 'market') renderHeroIndexChart();
      else {
        renderStockMainChart();
        if (state.detailTab === 'chips') renderInstChipsCanvas(-1);
        if (state.detailTab === 'fund') renderRevenueCanvas(-1);
      }
    });

    window.addEventListener('DOMContentLoaded', () => {
      initAllData();
      updateBreadcrumbs();
      updateHeroIndexHeader();
      renderHeroIndexChart();
      renderHeavyweightList();
      renderSectorHeatmap();
      renderScreenerTable();

      initHeroCanvasInteractions();
      initStockCanvasInteractions();
      initSubTabCanvasHover();

      startSimLoop();
    });
  </script>
</body>
</html>
