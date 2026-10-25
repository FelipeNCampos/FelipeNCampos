# Manutenção do painel

O painel usa Python 3.12 ou superior e apenas a biblioteca padrão. O SVG é local e pode ser exibido no GitHub sem depender de um serviço externo de cartões. O Spotify permanece independente e opcional.

## Atualizar

```powershell
python -m unittest discover -s tests -v
python scripts/generate_metrics.py
```

O comando consulta apenas endpoints públicos. `GH_TOKEN`, se definido, é enviado exclusivamente para `api.github.com`. Sem token, as consultas ficam sujeitas ao limite anônimo da API; o gerador precisa de uma chamada de linguagens para cada repositório próprio. Não salve tokens em arquivos versionados.

Para reconstruir o SVG com a coleta salva, sem acesso à rede:

```powershell
python scripts/generate_metrics.py --input assets/metrics/data.json
```

## Atualização no GitHub

Depois de publicar os arquivos em `main`, o workflow **Atualizar painel do perfil** executa testes e coleta os dados. Ele também pode ser iniciado em **Actions → Atualizar painel do perfil → Run workflow** e é agendado para 00:23, 06:23, 12:23 e 18:23 UTC (21:23 do dia anterior, 03:23, 09:23 e 15:23 em São Paulo). O GitHub pode atrasar execuções ou desabilitar agendamentos após inatividade.

O workflow usa o `GITHUB_TOKEN` temporário do próprio Actions; não exige PAT ou secret personalizado. O job de atualização pede `contents: write` para versionar apenas `assets/metrics/data.json` e `assets/metrics/dashboard.svg`. Políticas da organização ou proteção de `main` podem impedir o push; nesse caso, o log de Actions mostrará a falha. PRs executam apenas os testes, sem atualização ou permissão de escrita.

## Limites dos dados

- O calendário é lido do HTML público do GitHub, relacionando cada célula ao seu tooltip. Mudanças nesse HTML podem exigir ajuste no parser. Calendário incompleto ou contagens desconhecidas fazem a coleta falhar, preservando os arquivos anteriores.
- Contribuições visíveis podem incluir totais privados anonimizados. Os eventos e repositórios consultados são públicos.
- A API de eventos fornece uma janela limitada e até 300 eventos. Poucos eventos disponíveis produzem uma amostra pequena; o gráfico declara seu tamanho e intervalo, sem extrapolar para o ano.
- O agrupamento por hora usa UTC−3, o offset atual de São Paulo, apenas para eventos recentes. As datas do calendário seguem as datas fornecidas pelo GitHub.
- Linguagens são bytes classificados pelo GitHub, incluindo possíveis dependências que o serviço não tenha marcado como vendorizadas. Não equivalem a competência ou autoria individual.
- Uma falha de rede, limite da API ou parsing encerra o gerador antes de substituir a coleta anterior. A data no SVG permite identificar um painel desatualizado.

## Coleta inicial e referência

A coleta inicial foi realizada em 25/10/2026 usando Playwright, sem autenticação. Os mesmos endpoints alimentam o gerador Python nas atualizações seguintes. A apresentação usa fundo escuro, duas colunas, calendário isométrico e gráficos de atividade e linguagens, inspirados no [perfil de Fabr1n](https://github.com/Fabr1n/Fabr1n). Não foram reutilizados código do gerador, dados pessoais ou formação acadêmica da referência.

As descrições dos projetos foram verificadas nos READMEs públicos de [DiscordBot](https://github.com/FelipeNCampos/DiscordBot), [coletor Facebook](https://github.com/FelipeNCampos/guaia-facebook-collector-develop), [CRM](https://github.com/FelipeNCampos/CRM-Monolito-Micro_service) e [portfólio](https://github.com/FelipeNCampos/portifolio). Consulte a seção de metodologia do README para as fontes dos números.
