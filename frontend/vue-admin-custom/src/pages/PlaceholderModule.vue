<template>
  <div>
    <el-card>
      <h3>{{ title }}</h3>
      <p>This is an iframe placeholder for external module integration.</p>
      <div style="height:360px; border:1px dashed #dfe6ec; display:flex; align-items:center; justify-content:center; color:#999">iframe placeholder</div>
    </el-card>
  </div>
</template>

<script>
export default {
  computed: { title(){ return this.$route.name || 'Module' } }
}
</script>
