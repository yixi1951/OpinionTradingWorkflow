<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <div class="card-title">Total P&L</div>
          <div class="card-value">$12,345</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <div class="card-title">Today Return</div>
          <div class="card-value">+1.23%</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <div class="card-title">Open Positions</div>
          <div class="card-value">3</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top:16px">
      <div class="placeholder-chart">[Performance Chart Placeholder]</div>
    </el-card>

    <el-card style="margin-top:16px">
      <div class="table-title">Recent Trades</div>
      <el-table :data="trades" style="width:100%">
        <el-table-column prop="time" label="Time" width="180"/>
        <el-table-column prop="symbol" label="Symbol"/>
        <el-table-column prop="qty" label="Qty"/>
        <el-table-column prop="price" label="Price"/>
      </el-table>
    </el-card>
  </div>
</template>

<script>
export default {
  data(){
    return { trades: [
      {time:'2026-05-30 10:12', symbol:'AAPL', qty:1, price:172.5},
      {time:'2026-05-30 11:03', symbol:'TSLA', qty:2, price:621.1}
    ]}
  }
}
</script>

<style scoped>
.card-title{ color:#666 }
.card-value{ font-size:20px; margin-top:8px }
.placeholder-chart{ height:300px; display:flex; align-items:center; justify-content:center; color:#999 }
.table-title{ margin-bottom:12px; font-weight:600 }
</style>
