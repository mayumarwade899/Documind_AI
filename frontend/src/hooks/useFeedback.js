import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { submitFeedback, getFeedbackSummary, getNegativeFeedback } from '../services/queryService.js'
import toast from 'react-hot-toast'

export function useFeedback(days = 30) {
  const qc = useQueryClient()

  const summary = useQuery({
    queryKey: ['feedback-summary', days],
    queryFn: () => getFeedbackSummary(days),
    refetchInterval: 60_000,
  })

  const negative = useQuery({
    queryKey: ['negative-feedback', days],
    queryFn: () => getNegativeFeedback(days),
    refetchInterval: 60_000,
  })

  const submit = useMutation({
    mutationFn: submitFeedback,
    onSuccess: (_, variables) => {
      const label = variables.rating === 1 ? 'positive' : variables.rating === -1 ? 'negative' : 'neutral'
      toast.success(label === 'positive' ? 'Thanks for the feedback!' : 'Feedback recorded')
      qc.invalidateQueries({ queryKey: ['feedback-summary'] })
      qc.invalidateQueries({ queryKey: ['negative-feedback'] })
    },
    onError: (err) => toast.error(`Feedback failed: ${err.message}`),
  })

  return {
    summary: summary.data,
    negative: negative.data?.feedback ?? [],
    isLoading: summary.isLoading,
    submit: submit.mutate,
    isSubmitting: submit.isPending,
  }
}
