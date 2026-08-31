import { api, fetchCsrf } from "./client";

// Auth
// After register/login the server rotates the CSRF token; refresh our
// cookie immediately so the very next mutation can't fail with CSRF.
export const register = (username, password, email = "", fullName = "") =>
  api
    .post("/auth/register/", {
      username,
      password,
      full_name: fullName,
      ...(email ? { email } : {}),
    })
    .then(() => fetchCsrf());
export const login = (username, password) =>
  api.post("/auth/login/", { username, password }).then(() => fetchCsrf());
export const logout = () => api.post("/auth/logout/");
export const fetchMe = () => api.get("/auth/me/");
export const updateEmail = (email) => api.patch("/auth/me/", { email });
export const sendVerificationEmail = () => api.post("/auth/verify-email/send/");

// Public profile + sending
export const fetchPublicProfile = (username) =>
  api.get(`/users/${username}/`);
export const sendMessage = (username, message, senderName = "", image = null) => {
  if (image) {
    const fd = new FormData();
    fd.append("username", username);
    fd.append("message", message);
    if (senderName) fd.append("sender_name", senderName);
    fd.append("image", image);
    return api.post("/messages/", fd);
  }
  return api.post("/messages/", {
    username,
    message,
    ...(senderName ? { sender_name: senderName } : {}),
  });
};

// Recipient-only image endpoint (session-protected, same origin).
export const messageImageUrl = (id) => `/api/messages/${id}/image/`;

// Public stats
export const fetchStats = () => api.get("/stats/");

// Inbox & messages
export const fetchInbox = () => api.get("/messages/inbox/");
export const fetchSent = () => api.get("/messages/sent/");
export const readMessage = (id) => api.patch(`/messages/${id}/`);
export const deleteMessage = (id) => api.delete(`/messages/${id}/`);
// حذف الرسالة من صندوق الطرف الآخر (ميزة الاشتراك الموثق)
export const deleteForRecipient = (id) =>
  api.delete(`/messages/${id}/delete-for-recipient/`);
export const reportMessage = (id, reason, note = "") =>
  api.post(`/messages/${id}/report/`, { reason, note });
// رد المُستقبِل على رسالة (مشفَّر مثل الرسالة تمامًا)
export const replyToMessage = (id, reply) =>
  api.post(`/messages/${id}/reply/`, { reply });

// Settings
export const fetchSettings = () => api.get("/settings/");
export const patchSettings = (data) => api.patch("/settings/", data);
export const toggleAnonymous = () => api.post("/settings/toggle-anonymous/");

// Profile (real name + bio + avatar)
export const fetchMyProfile = () => api.get("/settings/profile/");
export const patchMyProfile = (data) => api.patch("/settings/profile/", data);
export const uploadAvatar = (file) => {
  const fd = new FormData();
  fd.append("avatar", file);
  return api.post("/settings/profile/avatar/", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};
// خيار إلغاء الصورة
export const removeAvatar = () => api.delete("/settings/profile/avatar/");

// Premium subscription (توثيق الحساب + كشف اسم المرسل)
export const subscribe = (transferNote = "") =>
  api.post("/settings/subscribe/", { transfer_note: transferNote });
export const fetchSubscriptionStatus = () =>
  api.get("/settings/subscribe/status/");