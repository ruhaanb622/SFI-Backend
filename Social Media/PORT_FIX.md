# 🔧 WRONG PORT - Quick Fix!

## 🚨 THE PROBLEM

**Your frontend is calling:** `localhost:8585` ❌  
**Your backend is running on:** `localhost:8423` ✅

**Result:** 401 errors because you're hitting the wrong server!

---

## ✅ THE FIX

### **Update Your Frontend Config File**

In your **FRONTEND repository** (not the backend!), find and edit:

```
assets/js/api/config.js
```

**Change the port from `8585` to `8423`:**

```javascript
// BEFORE (Wrong):
const javaURI = "http://localhost:8585";

// AFTER (Correct):
const javaURI = "http://localhost:8423";
```

---

## 📍 Where to Find This File

**Location:** `~/pages/assets/js/api/config.js`

Or wherever your frontend repository is located.

---

## 🔍 Example Config File

Your `config.js` should look something like this:

```javascript
// Backend API Configuration
export const javaURI = "http://localhost:8423";  // ← Make sure it's 8423!

export const fetchOptions = {
    method: 'GET',
    mode: 'cors',
    cache: 'default',
    credentials: 'include',
    headers: {
        'Content-Type': 'application/json',
    },
};
```

---

## 🧪 How to Test

### **Step 1: Update the Config**
Edit `assets/js/api/config.js` and change `8585` → `8423`

### **Step 2: Refresh Browser**
Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)

### **Step 3: Check Console**
Open browser console (F12) and you should see:
- ✅ No more 401 errors!
- ✅ Posts load successfully!

---

## 🎯 Quick Verification

### **Test Backend is Working:**
```bash
curl http://localhost:8423/api/post/all
# Should return: []
```

### **Test Wrong Port:**
```bash
curl http://localhost:8585/api/post/all
# Will fail or give wrong response
```

---

## 📊 Port Summary

| Service | Port | Status |
|---------|------|--------|
| **Flask Backend** | **8423** | ✅ Correct - Use this! |
| Something else | 8585 | ❌ Wrong - Don't use |

---

## 🔧 Common Config File Locations

Depending on your frontend setup:

```bash
# Jekyll/GitHub Pages:
~/pages/assets/js/api/config.js

# React:
~/frontend/src/config/api.js

# Vue:
~/frontend/src/api/config.js

# Plain HTML:
~/frontend/js/config.js
```

---

## ⚠️ Important Notes

1. **Backend is on 8423** - This is confirmed and working ✅
2. **Don't change backend** - It's correct!
3. **Change frontend config** - Update to port 8423
4. **Restart frontend** - Refresh or restart dev server

---

## 🎉 After Fixing

Once you update the port to `8423`:

- ✅ No more 401 errors
- ✅ Posts will load
- ✅ Login will work
- ✅ You can create posts
- ✅ Everything works!

---

## 🆘 If You Can't Find config.js

### **Option 1: Search for it**
```bash
cd ~/pages  # or your frontend directory
find . -name "config.js" -o -name "api.js" | grep -v node_modules
```

### **Option 2: Search for the port number**
```bash
cd ~/pages
grep -r "8585" . --exclude-dir=node_modules
```

This will show you all files that reference port 8585.

### **Option 3: Create the config file**

If it doesn't exist, create `assets/js/api/config.js`:

```javascript
// Backend API Configuration
export const javaURI = "http://localhost:8423";

export const fetchOptions = {
    method: 'GET',
    mode: 'cors',
    cache: 'default',
    credentials: 'include',
    headers: {
        'Content-Type': 'application/json',
    },
};
```

---

## 🎯 Quick Fix Command

```bash
# Go to your frontend repo
cd ~/pages  # adjust path as needed

# Find and replace 8585 with 8423
find assets -name "*.js" -type f -exec sed -i '' 's/8585/8423/g' {} +

# Refresh your browser
# Done!
```

---

## 📝 Summary

| What | Where | Change |
|------|-------|--------|
| **Backend** | Flask (running) | Port **8423** ✅ |
| **Frontend Config** | `config.js` | Change to **8423** ❌→✅ |
| **Browser** | Refresh | Hard refresh required |

---

## 🎊 You're Almost There!

Just update that one line in your frontend config from `8585` to `8423` and everything will work!

**The backend is perfect - just need to point the frontend to the right port!** 🎯

