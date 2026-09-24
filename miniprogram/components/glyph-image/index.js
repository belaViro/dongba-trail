Component({ properties: { src: String, name: String }, data: { failed: false }, observers: { src() { this.setData({ failed: false }) } }, methods: { fail() { this.setData({ failed: true }) } } })

