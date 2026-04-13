<template>
  <section class="content-card">
    <h1 class="page-title">帮助</h1>
    <div class="placeholder">
      <div class="placeholder-icon">?</div>
      <div class="placeholder-text">帮助内容后续补充。</div>
      <div class="placeholder-desc">这里保留和旧版一致的页面入口与占位位置。</div>
    </div>
  </section>
</template>

<style scoped>
.content-card {
  padding: 24px;
  border: 1px solid #d8e1dd;
  border-radius: 8px;
  background: #fff;
}

.page-title {
  margin: 0 0 24px;
  color: #1f2d28;
  font-size: 28px;
}

.placeholder {
  display: grid;
  justify-items: center;
  gap: 10px;
  min-height: 200px;
  align-content: center;
}

.placeholder-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: 8px;
  background: #eef8f7;
  color: #0f8b8d;
  font-size: 24px;
  font-weight: 700;
}

.placeholder-text {
  color: #213029;
  font-size: 16px;
  font-weight: 600;
}

.placeholder-desc {
  color: #70837c;
}
</style>
