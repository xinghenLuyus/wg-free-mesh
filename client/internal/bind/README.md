# bind

`internal/bind` 实现 `wfmctl bind` 的 HTTP 调用。

HTTP 只用于首次绑定。绑定成功后，客户端运行期通信全部走 MQTT。

