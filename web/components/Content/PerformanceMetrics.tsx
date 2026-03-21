'use client';

import React, { useState } from 'react';
import { PerformanceMetrics as PerformanceMetricsType } from '@/lib/api';

interface PerformanceMetricsProps {
  metrics: PerformanceMetricsType | null;
  isVisible: boolean;
}

export default function PerformanceMetrics({ metrics, isVisible }: PerformanceMetricsProps) {
  const [showDetails, setShowDetails] = useState(false);

  if (!isVisible || !metrics) return null;

  const formatTime = (ms: number | null | undefined) => {
    if (ms === null || ms === undefined) return '-';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getSpeedColor = (ms: number) => {
    if (ms < 500) return '#22c55e'; // 绿色 - 快
    if (ms < 1500) return '#eab308'; // 黄色 - 中等
    return '#ef4444'; // 红色 - 慢
  };

  const containerStyle: React.CSSProperties = {
    marginTop: '1.5rem',
    padding: '1rem',
    backgroundColor: '#f8fafc',
    borderRadius: '0.75rem',
    border: '1px solid #e2e8f0',
  };

  const headerStyle: React.CSSProperties = {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: '#475569',
    marginBottom: '0.75rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '0.5rem',
  };

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
    gap: '0.75rem',
  };

  const metricCardStyle = (value: number | null | undefined): React.CSSProperties => ({
    padding: '0.75rem',
    backgroundColor: 'white',
    borderRadius: '0.5rem',
    border: '1px solid #e2e8f0',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  });

  const labelStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    color: '#64748b',
    fontWeight: 500,
  };

  const valueStyle = (ms: number | null | undefined): React.CSSProperties => ({
    fontSize: '1.125rem',
    fontWeight: 700,
    color: typeof ms === 'number' ? getSpeedColor(ms) : '#94a3b8',
  });

  const toggleButtonStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    color: '#3b82f6',
    cursor: 'pointer',
    background: 'none',
    border: 'none',
    padding: '0.25rem 0.5rem',
  };

  const detailsStyle: React.CSSProperties = {
    marginTop: '0.75rem',
    padding: '0.75rem',
    backgroundColor: 'white',
    borderRadius: '0.5rem',
    border: '1px solid #e2e8f0',
  };

  const sectionTitleStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#475569',
    marginBottom: '0.5rem',
    marginTop: '0.75rem',
  };

  const tableStyle: React.CSSProperties = {
    width: '100%',
    fontSize: '0.75rem',
    borderCollapse: 'collapse',
  };

  const thStyle: React.CSSProperties = {
    textAlign: 'left',
    padding: '0.25rem',
    color: '#64748b',
    fontWeight: 500,
    borderBottom: '1px solid #e2e8f0',
  };

  const tdStyle: React.CSSProperties = {
    padding: '0.25rem',
    color: '#374151',
    borderBottom: '1px solid #f1f5f9',
  };

  // 计算总token使用量
  const totalTokens = metrics.token_usage
    ? Object.values(metrics.token_usage).reduce((sum, usage) => sum + usage.total_tokens, 0)
    : 0;

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          性能指标
        </div>
        <button style={toggleButtonStyle} onClick={() => setShowDetails(!showDetails)}>
          {showDetails ? '收起详情' : '查看详情'}
        </button>
      </div>

      <div style={gridStyle}>
        <div style={metricCardStyle(metrics.first_token_latency_ms)}>
          <span style={labelStyle}>首字延迟</span>
          <span style={valueStyle(metrics.first_token_latency_ms)}>
            {formatTime(metrics.first_token_latency_ms)}
          </span>
        </div>
        <div style={metricCardStyle(metrics.inference_time_ms)}>
          <span style={labelStyle}>推理时间</span>
          <span style={valueStyle(metrics.inference_time_ms)}>
            {formatTime(metrics.inference_time_ms)}
          </span>
        </div>
        <div style={metricCardStyle(metrics.search_time_ms)}>
          <span style={labelStyle}>搜索时间</span>
          <span style={valueStyle(metrics.search_time_ms)}>
            {formatTime(metrics.search_time_ms)}
          </span>
        </div>
        <div style={metricCardStyle(metrics.total_time_ms)}>
          <span style={labelStyle}>总耗时</span>
          <span style={valueStyle(metrics.total_time_ms)}>
            {formatTime(metrics.total_time_ms)}
          </span>
        </div>
      </div>

      {/* Token 使用量 */}
      {totalTokens > 0 && (
        <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.75rem' }}>
          <div style={{
            flex: 1,
            padding: '0.75rem',
            backgroundColor: 'white',
            borderRadius: '0.5rem',
            border: '1px solid #e2e8f0',
          }}>
            <span style={labelStyle}>Token 使用量</span>
            <div style={valueStyle(totalTokens)}>{totalTokens.toLocaleString()}</div>
          </div>
          {metrics.api_calls && (
            <div style={{
              flex: 1,
              padding: '0.75rem',
              backgroundColor: 'white',
              borderRadius: '0.5rem',
              border: '1px solid #e2e8f0',
            }}>
              <span style={labelStyle}>API 调用次数</span>
              <div style={valueStyle(
                (metrics.api_calls.spotify_search || 0) + (metrics.api_calls.llm_calls || 0)
              )}>
                {(metrics.api_calls.spotify_search || 0) + (metrics.api_calls.llm_calls || 0)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 详细指标 */}
      {showDetails && metrics.node_timings && Object.keys(metrics.node_timings).length > 0 && (
        <div style={detailsStyle}>
          <div style={sectionTitleStyle}>节点执行时间详情</div>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>节点名称</th>
                <th style={thStyle}>调用次数</th>
                <th style={thStyle}>总耗时</th>
                <th style={thStyle}>平均耗时</th>
                <th style={thStyle}>最大耗时</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.node_timings).map(([name, timing]) => (
                <tr key={name}>
                  <td style={tdStyle}>{name}</td>
                  <td style={tdStyle}>{timing.count}</td>
                  <td style={tdStyle}>{formatTime(timing.total_ms)}</td>
                  <td style={tdStyle}>{formatTime(timing.avg_ms)}</td>
                  <td style={tdStyle}>{formatTime(timing.max_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {metrics.token_usage && Object.keys(metrics.token_usage).length > 0 && (
            <>
              <div style={sectionTitleStyle}>Token 使用详情</div>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>提供商</th>
                    <th style={thStyle}>Prompt Tokens</th>
                    <th style={thStyle}>Completion Tokens</th>
                    <th style={thStyle}>总计</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(metrics.token_usage).map(([provider, usage]) => (
                    <tr key={provider}>
                      <td style={tdStyle}>{provider}</td>
                      <td style={tdStyle}>{usage.prompt_tokens.toLocaleString()}</td>
                      <td style={tdStyle}>{usage.completion_tokens.toLocaleString()}</td>
                      <td style={tdStyle}>{usage.total_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}
