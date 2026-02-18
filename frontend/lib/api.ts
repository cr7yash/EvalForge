import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

export const evaluationsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    api.get('/evaluations', { params }),

  get: (id: string) =>
    api.get(`/evaluations/${id}`),

  create: (data: any) =>
    api.post('/evaluations', data),

  delete: (id: string) =>
    api.delete(`/evaluations/${id}`),
}

export const providersApi = {
  list: () =>
    api.get('/providers'),

  listEvaluators: () =>
    api.get('/providers/evaluators'),
}
