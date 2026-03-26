import { NextRequest } from 'next/server';

const API_BASE_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8501';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = searchParams.get('limit') || '20';

    const response = await fetch(`${API_BASE_URL}/api/logs?limit=${limit}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`);
    }

    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('Logs proxy error:', error);
    return new Response(
      JSON.stringify({ error: 'Failed to connect to backend' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
