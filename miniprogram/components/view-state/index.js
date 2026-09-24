Component({
  properties: { loading: Boolean, error: String, empty: Boolean, emptyText: { type: String, value: '暂无内容' }, requestId: String },
  methods: { retry() { this.triggerEvent('retry') } }
})

