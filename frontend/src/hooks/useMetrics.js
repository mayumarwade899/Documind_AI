import { useQuery } from '@tanstack/react-query'
import { getMetrics, getDailyMetrics, getLatency } from '../services/metricsService.js'

export function useMetrics(days = 7) {
  const metrics = useQuery({
    queryKey: ['metrics', days],
    queryFn: () => getMetrics(days),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const daily = useQuery({
    queryKey: ['daily-metrics', days],
    queryFn: () => getDailyMetrics(days),
    refetchInterval: 60_000,
  })

  const latency = useQuery({
    queryKey: ['latency', days],
    queryFn: () => getLatency(days),
    refetchInterval: 30_000,
  })

  return {
    metrics: metrics.data,
    daily: daily.data?.days ?? [],
    latency: latency.data,
    isLoading: metrics.isLoading,
    isError: metrics.isError,
    refetch: metrics.refetch,
  }
}
