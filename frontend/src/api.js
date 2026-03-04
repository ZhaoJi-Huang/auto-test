import axios from 'axios'

const api = axios.create({ timeout: 30000 })

// 设备配置
export const getConfig = () => api.get('/api/tv/config')
export const updateConfig = (data) => api.post('/api/tv/config', data)
export const getCaptureDevices = () => api.get('/api/tv/capture-devices', { timeout: 120000 })
export const checkDevice = () => api.get('/api/tv/device/check')
export const getInputDevices = () => api.get('/api/tv/input-devices', { timeout: 15000 })

// 用例管理
export const getCases = (params) => api.get('/api/tv/cases', { params })
export const getCase = (key) => api.get(`/api/tv/cases/${key}`)
export const importByJql = (jql) => api.post('/api/tv/cases/import/jql', { jql })
export const importByKey = (key) => api.post('/api/tv/cases/import/key', { key })
export const syncCase = (key) => api.post(`/api/tv/cases/sync/${key}`)
export const createCase = (data) => api.post('/api/tv/cases/create', data)
export const updateCase = (key, data) => api.put(`/api/tv/cases/${key}`, data)
export const copyCase = (key) => api.post(`/api/tv/cases/${key}/copy`)
export const deleteCase = (key) => api.delete(`/api/tv/cases/${key}`)

// Jira 配置
export const getJiraConfig = () => api.get('/api/tv/jira/config')
export const saveJiraConfig = (data) => api.post('/api/tv/jira/config', data)

// 录制
export const startRecording = (case_key) => api.post('/api/tv/recording/start', { case_key })
export const stopRecording = () => api.post('/api/tv/recording/stop')
export const getRecordingStatus = () => api.get('/api/tv/recording/status')
export const insertAdb = (command, description) => api.post('/api/tv/recording/insert_adb', { command, description })
export const insertAi = (type, prompt) => api.post('/api/tv/recording/insert_ai', { type, prompt })
export const deleteLastStep = () => api.post('/api/tv/recording/delete_last')
export const insertStepAt = (index, type, params) => api.post('/api/tv/recording/insert_step_at', { index, type, ...params })
export const deleteStep = (index) => api.post('/api/tv/recording/delete_step', { index })
export const getSavedSteps = (caseKey) => api.get(`/api/tv/recording/saved_steps/${caseKey}`)
export const insertSavedStep = (caseKey, index, type, params) => api.post(`/api/tv/recording/saved_steps/${caseKey}/insert`, { index, type, ...params })
export const deleteSavedStep = (caseKey, index) => api.post(`/api/tv/recording/saved_steps/${caseKey}/delete`, { index })
export const updateSavedStep = (caseKey, index, type, params) => api.post(`/api/tv/recording/saved_steps/${caseKey}/update`, { index, type, ...params })

// 遥控器
export const sendKey = (key) => api.post('/api/tv/recording/send_key', { key })

// 快速回放（录制页面用）
export const quickReplay = (caseKey) => api.post('/api/tv/recording/quick_replay', { case_key: caseKey })
export const stopQuickReplay = () => api.post('/api/tv/recording/quick_replay/stop')

// 回放
export const startReplay = (data) => api.post('/api/tv/replay/start', data)
export const stopReplay = () => api.post('/api/tv/replay/stop')
export const getReplayStatus = () => api.get('/api/tv/replay/status')
export const getReplayResults = (caseKey) => api.get(`/api/tv/replay/results/${caseKey}`)
export const getReplayResult = (caseKey, timestamp) => api.get(`/api/tv/replay/result/${caseKey}/${timestamp}`)
export const getRunResult = (caseKey, timestamp, runIndex) => api.get(`/api/tv/replay/result/${caseKey}/${timestamp}/run/${runIndex}`)

// 测试计划
export const getPlans = () => api.get('/api/tv/plans')
export const getPlan = (id) => api.get(`/api/tv/plans/${id}`)
export const createPlan = (data) => api.post('/api/tv/plans', data)
export const updatePlan = (id, data) => api.put(`/api/tv/plans/${id}`, data)
export const deletePlan = (id) => api.delete(`/api/tv/plans/${id}`)
export const runPlan = (id, data) => api.post(`/api/tv/plans/${id}/run`, data)
export const stopPlan = (id) => api.post(`/api/tv/plans/${id}/stop`)
export const getPlanStatus = (id) => api.get(`/api/tv/plans/${id}/status`)
export const getPlanResults = (id) => api.get(`/api/tv/plans/${id}/results`)

// 统计
export const getStats = () => api.get('/api/tv/stats')

// Git
export const gitCommit = (data) => api.post('/api/tv/git/commit', data)
export const gitPull = () => api.post('/api/tv/git/pull')
export const gitStatus = () => api.get('/api/tv/git/status')
export const gitLog = () => api.get('/api/tv/git/log')
