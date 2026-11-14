import axios from 'axios'

/**
 * Axios instance configured to communicate directly with FastAPI backend at http://127.0.0.1:8000.
 */
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '')

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30_000,
})

// Error response interceptor to extract human-readable error messages from FastAPI
api.interceptors.response.use(
  (response) => response,
  (error) => {
    let message = 'An unexpected error occurred.'

    if (error.response) {
      // FastAPI typically sends error details in error.response.data.detail
      const data = error.response.data
      if (typeof data?.detail === 'string') {
        message = data.detail
      } else if (Array.isArray(data?.detail)) {
        // Pydantic validation errors
        message = data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ')
      } else if (data?.message) {
        message = data.message
      } else {
        message = `Server responded with status ${error.response.status}: ${error.response.statusText}`
      }
    } else if (error.request) {
      message = `Cannot connect to backend server. Please ensure the backend is running at ${API_BASE_URL}.`
    } else if (error.message) {
      message = error.message
    }

    return Promise.reject(new Error(message))
  },
)

export default api
