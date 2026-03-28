'use client';

import { motion, useMotionValue, useTransform } from 'framer-motion';
import { theme } from '@/styles/theme';

interface ProductIntroProps {
  onPrimaryAction?: () => void;
  onSecondaryAction?: () => void;
  onQuickExampleSelect?: (prompt: string) => void;
}

const insightStats = [
  {
    label: '理解能力',
    value: '心情 / 场景 / 流派',
    hint: 'LangGraph + LLM 意图识别',
    icon: '🧠',
  },
  {
    label: '推荐链路',
    value: 'Spotify + 网络搜索',
    hint: 'MCP 直连官方 API',
    icon: '🔗',
  },
  {
    label: '交互体验',
    value: 'SSE 流式输出',
    hint: '逐词推荐说明 + 逐首上屏',
    icon: '⚡',
  },
];

const quickExamples = [
  { title: '给加班夜写代码的人推荐稳态节奏', meta: '心情：专注 / 场景：深夜' },
  { title: '我想在雨天窗边听些治愈的独立民谣', meta: '联动心情 + 流派' },
  { title: '根据周杰伦帮我找一些同样浪漫的中文 R&B', meta: '歌手 + 风格' },
];

const heroTags = ['心情理解', '场景推荐', 'SSE 流式', 'Spotify 接入'];

// Magnetic Button Component
const MagneticButton = ({
  children,
  onClick,
  className = '',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const handleMouseMove = (event: React.MouseEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    x.set((event.clientX - centerX) * 0.1);
    y.set((event.clientY - centerY) * 0.1);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.button
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ x, y }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className={className}
    >
      {children}
    </motion.button>
  );
};

export default function ProductIntro({
  onPrimaryAction,
  onSecondaryAction,
  onQuickExampleSelect,
}: ProductIntroProps) {
  return (
    <section className="flex-1 w-full flex items-center justify-center px-6 py-12 md:px-12 md:py-16 lg:px-20 lg:py-20">
      <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-5 gap-6 lg:gap-8">
        {/* Hero Card - Left Side */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="lg:col-span-3 relative overflow-hidden rounded-3xl bg-gradient-to-br from-dark-primary via-dark-secondary to-dark-tertiary p-8 md:p-10 lg:p-12 text-white shadow-2xl"
        >
          {/* Animated Background Gradient */}
          <div className="absolute inset-0 bg-gradient-mesh opacity-40 animate-pulse-slow" />

          {/* Glow Effect */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/20 rounded-full blur-3xl" />

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="relative z-10"
          >
            {/* Status Badge */}
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 text-sm font-medium mb-6">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(74,222,128,0.8)]" />
              音乐推荐 Agent 已就绪
            </span>

            {/* Headline */}
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-tight mb-6">
              用一句自然语言
              <br />
              <span className="gradient-text">即刻生成专属音乐推荐。</span>
            </h1>

            {/* Description */}
            <p className="text-base md:text-lg text-white/80 leading-relaxed max-w-2xl mb-8">
              基于 LangGraph 工作流 + Spotify/MCP + Tavily 搜索，自动理解心情、场景和喜好，串联搜索、推荐与解释，让每一首歌的理由都清晰可见。
            </p>

            {/* Tags */}
            <div className="flex flex-wrap gap-3 mb-10">
              {heroTags.map((tag, index) => (
                <motion.span
                  key={tag}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.4 + index * 0.1, duration: 0.4 }}
                  className="px-4 py-2 rounded-full text-sm font-medium border border-white/20 bg-white/5 backdrop-blur-sm"
                >
                  {tag}
                </motion.span>
              ))}
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-wrap gap-4">
              <MagneticButton
                onClick={onPrimaryAction}
                className="px-8 py-4 rounded-full font-semibold text-dark-primary bg-emerald-400 shadow-lg shadow-emerald-500/30 hover:shadow-emerald-500/50 transition-shadow"
              >
                进入推荐体验
              </MagneticButton>

              <MagneticButton
                onClick={onSecondaryAction}
                className="px-8 py-4 rounded-full font-medium text-white border-2 border-white/30 hover:border-white/50 hover:bg-white/5 transition-all"
              >
                查看使用指南
              </MagneticButton>
            </div>
          </motion.div>
        </motion.div>

        {/* Right Side - Stats & Examples */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Stats Grid */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="rounded-2xl bg-white border border-light-tertiary p-6 shadow-lg"
          >
            <div className="grid grid-cols-1 gap-5">
              {insightStats.map((stat, index) => (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + index * 0.1, duration: 0.4 }}
                  className="flex items-start gap-4 p-4 rounded-xl bg-light-primary hover:bg-light-secondary transition-colors"
                >
                  <span className="text-3xl">{stat.icon}</span>
                  <div className="flex-1">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {stat.label}
                    </span>
                    <p className="text-lg font-semibold text-dark-primary mt-1">{stat.value}</p>
                    <p className="text-sm text-gray-600 mt-0.5">{stat.hint}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Quick Examples */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.6 }}
            className="rounded-2xl bg-white border border-light-tertiary p-6 shadow-lg flex-1"
          >
            <div className="flex justify-between items-center mb-5">
              <div>
                <p className="text-lg font-semibold text-dark-primary">快速灵感</p>
                <p className="text-sm text-gray-500 mt-0.5">点击示例即可注入输入框</p>
              </div>
              <span className="text-xs text-gray-400 bg-light-secondary px-3 py-1.5 rounded-full">
                Shift + Enter 换行
              </span>
            </div>

            <div className="space-y-3">
              {quickExamples.map((example, index) => (
                <motion.div
                  key={example.title}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.6 + index * 0.1, duration: 0.4 }}
                  className="group rounded-xl p-4 bg-light-primary border border-transparent hover:border-emerald-300 hover:shadow-md transition-all cursor-pointer"
                  onClick={() => onQuickExampleSelect?.(example.title)}
                >
                  <div className="flex justify-between items-start gap-3">
                    <div className="flex-1">
                      <p className="font-semibold text-dark-primary group-hover:text-emerald-700 transition-colors">
                        {example.title}
                      </p>
                      <p className="text-sm text-gray-600 mt-1">{example.meta}</p>
                    </div>
                    <span className="text-xs font-medium px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 group-hover:bg-emerald-100 transition-colors whitespace-nowrap">
                      注入提示
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Demo CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="rounded-2xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 p-5 shadow-md"
          >
            <div className="flex justify-between items-center">
              <div>
                <p className="font-semibold text-dark-primary">流程提示</p>
                <p className="text-sm text-gray-600 mt-0.5">
                  先从「产品首页」了解流转，再进入场景操作。
                </p>
              </div>
              <button className="px-5 py-2.5 rounded-full border border-emerald-300 bg-white text-emerald-700 font-medium text-sm hover:bg-emerald-50 transition-colors">
                查看 Demo
              </button>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
