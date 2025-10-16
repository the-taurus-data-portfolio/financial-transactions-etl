1. Ознакомся с проектом. Для это прочитай следующие файлы: 
  - [README.md](../README.md)
  - [specification.md](specification.md)

2. Теперь посмотри, на конфигурационные файлы для одного из банков: Swedbank
   - [swedbank_source.yaml](../schemas/swedbank_source.yaml)
   - [swedbank_to_intermediate.yaml](../mappings/swedbank_to_intermediate.yaml)
   - [statement (43).csv](../data/transactions/swedbank/statement%20(43).csv) (пример выписки из банка)
3. На базе этого сделай изменения в конфигурационных файлах для другого банка: SEB
   - [kontovv (6).csv](../data/transactions/seb/kontovv%20(6).csv) пример выписки из банка (не нужно менять)
   - [seb_source.yaml](../schemas/seb_source.yaml)
   - [seb_to_intermediate.yaml](../mappings/seb_to_intermediate.yaml)