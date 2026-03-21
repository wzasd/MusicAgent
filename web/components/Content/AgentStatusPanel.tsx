'use client';

import React from 'react';
import { AgentStatusEvent } from '@/lib/api';

interface AgentStatusPanelProps {
  status: AgentStatusEvent | null;
  isVisible: boolean;
}

export default function AgentStatusPanel({ status, isVisible }: AgentStatusPanelProps) {
  if (!isVisible) return null;

  // 节点名称映射（中文显示）
  const nodeNameMap: Record<string, string> = {
    'analyze_intent': '意图分析',
    'search_songs': '歌曲搜索',
    'generate_recommendations': '生成推荐',
    'analyze_user_preferences': '分析用户偏好',
    'enhanced_recommendations': '增强推荐',
    'create_playlist': '创建播放列表',
    'general_chat': '通用对话',
    'generate_explanation': '生成解释',
  };

  // 状态样式
  const getStatusColor = (nodeStatus: string) => {
    switch (nodeStatus) {
      case 'completed':
        return '#22c55e'; // 绿色
      case 'running':
        return '#3b82f6'; // 蓝色
      case 'failed':
        return '#ef4444'; // 红色
      case 'skipped':
        return '#94a3b8'; // 灰色
      default:
        return '#e2e8f0'; // 浅灰
    }
  };

  const getStatusIcon = (nodeStatus: string) => {
    switch (nodeStatus) {
      case 'completed':
        return '✓';
      case 'running':
        return '●';
      case 'failed':
        return '✗';
      case 'skipped':
        return '−';
      default:
        return '○';
    }
  };

  // 容器样式
  const containerStyle: React.CSSProperties = {
    marginTop: '1rem',
    padding: '1rem',
    backgroundColor: '#f8fafc',
    borderRadius: '0.75rem',
    border: '1px solid #e2e8f0',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '0.75rem',
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: '#475569',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  };

  const requestIdStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    color: '#94a3b8',
    fontFamily: 'monospace',
  };

  // 进度条样式
  const progressContainerStyle: React.CSSProperties = {
    marginBottom: '0.75rem',
  };

  const progressBarStyle = (progress: number): React.CSSProperties => ({
    height: '4px',
    backgroundColor: '#e2e8f0',
    borderRadius: '2px',
    overflow: 'hidden',
    marginBottom: '0.5rem',
  });

  const progressFillStyle = (progress: number): React.CSSProperties => ({
    height: '100%',
    width: `${progress}%`,
    backgroundColor: progress === 100 ? '#22c55e' : '#3b82f6',
    borderRadius: '2px',
    transition: 'width 0.3s ease',
  });

  const progressTextStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    color: '#64748b',
    textAlign: 'center',
  };

  // 当前节点样式
  const currentNodeStyle: React.CSSProperties = {
    padding: '0.5rem 0.75rem',
    backgroundColor: '#eff6ff',
    borderRadius: '0.5rem',
    marginBottom: '0.75rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '0.875rem',
    color: '#1e40af',
  };

  const runningDotStyle: React.CSSProperties = {
    width: '8px',
    height: '8px',
    backgroundColor: '#3b82f6',
    borderRadius: '50%',
    animation: 'pulse 1s infinite',
  };

  // 节点历史列表样式
  const historyListStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.375rem',
  };

  const historyItemStyle = (nodeStatus: string): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.375rem 0.5rem',
    borderRadius: '0.375rem',
    fontSize: '0.8125rem',
    backgroundColor: nodeStatus === 'running' ? '#eff6ff' : 'transparent',
    transition: 'background-color 0.2s',
  });

  const iconStyle = (nodeStatus: string): React.CSSProperties => ({
    width: '16px',
    height: '16px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: getStatusColor(nodeStatus),
    fontSize: nodeStatus === 'running' ? '10px' : '12px',
    fontWeight: 'bold',
  });

  const nodeNameStyle: React.CSSProperties = {
    flex: 1,
    color: '#374151',
  };

  const durationStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    color: '#94a3b8',
    fontFamily: 'monospace',
  };

  // 总体状态样式
  const overallStatusStyle = (overallStatus: string): React.CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.25rem',
    padding: '0.25rem 0.5rem',
    borderRadius: '0.25rem',
    fontSize: '0.75rem',
    fontWeight: 500,
    backgroundColor:
      overallStatus === 'completed' ? '#dcfce7' :
      overallStatus === 'failed' ? '#fee2e2' :
      overallStatus === 'running' ? '#dbeafe' : '#f1f5f9',
    color:
      overallStatus === 'completed' ? '#166534' :
      overallStatus === 'failed' ? '#991b1b' :
      overallStatus === 'running' ? '#1e40af' : '#64748b',
  });

  // 如果没有状态，显示加载中
  if (!status) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <span style={titleStyle}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v6m0 6v6m4.22-10.22l4.24-4.24M6.34 6.34L2.1 2.1m17.8 17.8l-4.24-4.24M6.34 17.66l-4.24 4.24M23 12h-6m-6 0H1m20.24-4.24l-4.24 4.24M6.34 6.34l-4.24-4.24" />
            </svg>
            Agent 状态
          </span>
        </div>
        <div style={{ textAlign: 'center', padding: '1rem', color: '#94a3b8' }}>
          等待 Agent 启动...
        </div>
      </div>
    );
  }

  // 计算进度
  const progress = status.total_nodes > 0
    ? Math.round((status.nodes_executed / status.total_nodes) * 100)
    : 0;

  // 过滤出已执行或有状态的节点
  const visibleNodes = status.node_history || [];

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v6m0 6v6m4.22-10.22l4.24-4.24M6.34 6.34L2.1 2.1m17.8 17.8l-4.24-4.24M6.34 17.66l-4.24 4.24M23 12h-6m-6 0H1m20.24-4.24l-4.24 4.24M6.34 6.34l-4.24-4.24" />
          </svg>
          Agent 状态
        </span>
        <span style={requestIdStyle}>#{status.request_id}</span>
      </div>

      {/* 总体状态 */}
      <div style={{ marginBottom: '0.75rem' }}>
        <span style={overallStatusStyle(status.overall_status)}>
          {status.overall_status === 'idle' && '⏸️ 空闲'}
          {status.overall_status === 'running' && '🔄 执行中'}
          {status.overall_status === 'completed' && '✅ 已完成'}
          {status.overall_status === 'failed' && '❌ 失败'}
        </span>
        {status.elapsed_ms && (
          <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', color: '#94a3b8' }}>
            {Math.round(status.elapsed_ms / 100) / 10}s
          </span>
        )}
      </div>

      {/* 进度条 */}
      <div style={progressContainerStyle}>
        <div style={progressBarStyle(progress)}>
          <div style={progressFillStyle(progress)} />
        </div>
        <div style={progressTextStyle}>
          已执行 {status.nodes_executed} / {status.total_nodes} 个节点
        </div>
      </div>

      {/* 当前执行节点 */}
      {status.current_node && status.overall_status === 'running' && (
        <div style={currentNodeStyle}>
          <span style={runningDotStyle} />
          <span>正在执行: {nodeNameMap[status.current_node] || status.current_node}</span>
        </div>
      )}

      {/* 节点执行历史 */}
      {visibleNodes.length > 0 && (
        <div style={historyListStyle}>
          {visibleNodes.map((node, index) => (
            <div key={`${node.node_name}-${index}`} style={historyItemStyle(node.status)}>
              <span style={iconStyle(node.status)}>{getStatusIcon(node.status)}</span>
              <span style={nodeNameStyle}>{nodeNameMap[node.node_name] || node.node_name}</span>
              {node.duration_ms && (
                <span style={durationStyle}>{Math.round(node.duration_ms)}ms</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 全局动画样式 */}
      <style jsx global>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
