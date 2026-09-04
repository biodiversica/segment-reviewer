# Revisor de Segmentos

[← English](README.md)

Uma ferramenta de linha de comando que serve uma **interface no navegador para
revisar uma pasta de segmentos de áudio**. Cada clipe aparece como espectrograma,
com o que sua pasta e seu nome de arquivo demonstram sobre ele; você escuta e marca
como **Verdadeiro** (correto) ou **Falso** (errado, com o rótulo correto). Os
clipes revisados são movidos para `verdadeiro/`, `falso/` ou `multi/` dentro da
pasta de segmentos e, opcionalmente, registrados numa tabela de anotações.

Funciona com qualquer conjunto de clipes, não importa como tenham sido gerados —
a saída de um detector, exemplos recortados à mão, as previsões de um
classificador a ser ser avalido. A pasta de segmentos pode ser **local** ou **remota via
SSH**, e a interface pode ser servida para **outra máquina** na sua rede local ou
Tailscale. A interface está disponível em **Português (Brasil)** e **Inglês**.

---

## Como um segmento é lido

Duas fontes independentes, ambas configuráveis:

**O nome da pasta fornece o rótulo.** Um conjunto revisado costuma ser organizado com uma
pasta por classe, então a pasta em que o clipe está é o rótulo que ele carrega:

```
segmentos/
├── PONTO_A/BOAALB/PONTO_A_20240115_053000_12.0_17.0_det1.wav   → rótulo BOAALB
├── PONTO_A/PHYLUT/PONTO_A_20240115_061500_3.5_8.5_det2.wav     → rótulo PHYLUT
└── chuva/POCA_20240116_200000_5.0_10.0_det4.wav                → rótulo chuva
```

As pastas acima do rótulo são mantidas como estão — `2024/campo/PONTO_A/BOAALB/`
rotula o clipe como `BOAALB` e lembra das três pastas acima dele. Um clipe
diretamente na pasta de segmentos simplesmente ainda não tem rótulo.

**A pasta da classe vem primeiro?** Alguns conjuntos são organizados ao
contrário, com os pontos *dentro* de cada pasta de classe. Diga qual nível carrega
o rótulo com `--label-depth`, contando a partir da pasta de segmentos: os pontos
abaixo dele continuam sendo pontos — não são oferecidos como rótulos, e o veredito
os recoloca sob o rótulo que você confirmou:

```
segmentos/                       # --label-depth 1
├── BOAALB/PONTO_A/clipe.wav     → rótulo BOAALB, a pasta PONTO_A é mantida
├── BOAALB/POCA/clipe.wav        → rótulo BOAALB
└── PHYLUT/clipe.wav             → rótulo PHYLUT (mais raso que o nível, ainda rotulado)
```

**O nome do arquivo fornece o resto das informações.** Por padrão um arquivo de áudio é lido como

```
[ponto]_[AAAAMMDD]_[HHMMSS]_[início]_[fim]_*
      PONTO_A_20240115_053000_12.0_17.0_det1.wav
```

- O ponto pode conter underscores — a referência é na data e na hora.
- `início`/`fim` são a posição do clipe, em segundos, dentro da gravação de onde
  ele foi cortado. Os dois separadores funcionam: `12.0_17.0` e `12.0-17.0s`.
- `_*` é qualquer outra coisa, mostrada na interface como *extra*.
- Tudo depois do ponto é opcional, e **um nome que não casa com nada continua
  perfeitamente revisável** — a interface apenas mostra menos sobre ele.

Nomeado de outro jeito? Escreva o formato com `--filename-pattern` — veja
[Outras convenções de nome](#outras-convenções-de-nome).

---

## Instalação

### Com [uv](https://docs.astral.sh/uv/) (recomendado)

Rodar sem instalar nada permanentemente:

```bash
uvx --from git+https://github.com/biodiversica/segment-reviewer segment-reviewer /caminho/dos/segmentos
```

Ou instalar como ferramenta:

```bash
uv tool install git+https://github.com/biodiversica/segment-reviewer
segment-reviewer /caminho/dos/segmentos
```

A partir de um clone, para desenvolvimento:

```bash
git clone https://github.com/biodiversica/segment-reviewer
cd segment-reviewer
uv venv
uv pip install -e ".[dev]"
uv run segment-reviewer /caminho/dos/segmentos
```

### Com pip

```bash
python -m venv .venv && source .venv/bin/activate
pip install git+https://github.com/biodiversica/segment-reviewer
segment-reviewer /caminho/dos/segmentos
```

Python 3.10 ou mais novo. A parte de áudio (librosa, soundfile) precisa da
`libsndfile`, que já vem nos wheels de Linux, macOS e Windows.

---

## Uso

```bash
# Pasta local, interface nesta máquina
segment-reviewer ~/segmentos --lang pt-BR

# Lista suspensa restrita a estes rótulos e tabela de anotações
segment-reviewer ~/segmentos --lang pt-BR --labels "BOAALB, PHYLUT, chuva" --annotations

# Segmentos num servidor, revisados do seu notebook
segment-reviewer ssh://usuario@servidor/dados/segmentos --lang pt-BR

# Servir a interface para a rede (rede local, Tailscale, …)
segment-reviewer /dados/segmentos --host 0.0.0.0 --port 8765
```

O comando imprime um resumo e a URL para abrir. Com `--host 0.0.0.0` ele também
imprime o endereço que as outras máquinas devem usar.

### No navegador

| Controle | O que faz |
| --- | --- |
| **Botões de rótulo** | Um botão por rótulo. Clique para marcá-lo neste segmento; clique de novo para desmarcar. O rótulo do próprio segmento já vem marcado, então aceitá-lo é um clique só. <kbd>1</kbd>…<kbd>9</kbd> acionam os nove primeiros. |
| **✔ Verdadeiro** | O rótulo está certo. O clipe mantém seu caminho, sob `verdadeiro/`. |
| **✘ Falso** | Errado. Arquivado sob a mesma seleção, em `falso/` em vez de `verdadeiro/` — então marque o(s) rótulo(s) correto(s) antes de apertar. Sem nada marcado, o clipe vai para `falso/desconhecido/`. |
| **← Anterior / Próximo →** | Navega sem decidir nada. |
| **Tipo / Hz mín / Hz máx / dB** | Atualiza o espectrograma na hora — eixo de frequência em mel, em Hz linear ou em Hz logarítmico. O player de áudio não é afetado, então o clipe continua tocando enquanto você muda a visualização. |
| **✎** | Edita a própria lista de rótulos: cada botão ganha um **×** para removê-lo, e a caixa abaixo adiciona um novo. As mudanças são salvas em `labels.txt`, na pasta de segmentos. |
| **⟳** | Relê a pasta, por exemplo quando chegam mais segmentos. |
| **Idioma** | Alterna a interface entre Português e Inglês. |

Os dois vereditos leem a mesma seleção — os botões dizem *o que* o clipe é, e
Verdadeiro ou Falso só diz em qual pasta ele será salvo. Após a conclusão da revisão do clipe, o mesmo é removido da lista de revisão e o próximo clipe aparecerá automaticamente. 

Um segmento pode receber vários rótulos — duas espécies cantando ao mesmo tempo —
o que é o padrão; `--no-multi-label` limita cada segmento a um rótulo. Você pode ajustar os rótulos disponíveis quando for necessário.

Teclado: <kbd>←</kbd> <kbd>→</kbd> para navegar, <kbd>T</kbd> / <kbd>F</kbd> para
verdadeiro/falso, <kbd>1</kbd>…<kbd>9</kbd> para marcar os nove primeiros
rótulos, <kbd>Espaço</kbd> para tocar ou pausar.

### A lista de rótulos

Os rótulos disponíveis vêm de uma lista salva em **`labels.txt`**, na pasta de segmentos, um
rótulo por linha. Na primeira vez que um conjunto é aberto, a lista é criada com
os rótulos que o conjunto já usa, e o arquivo é gravado; a partir
daí a referência principal é este arquivo, e você o edita pela interface (ou à mão — linhas em branco e comentários com `#` são ignorados).

Iniciar com `--labels` define outra coisa: só aqueles rótulos são oferecidos na
sessão, no lugar do que estiver no arquivo, e é essa lista que passa a ser gravada.

Nada é acrescentado automaticamente: uma releitura que encontre uma pasta nova
não adiciona o nome dela para a lista. Reduzir a lista também é seguro — o rótulo
do próprio clipe sempre aparece como botão, esteja ou não na lista, e digitar um
nome na caixa o adiciona à lista e o marca no segmento em visualização de uma vez.

Use `--labels-file` para guardar a lista em outro lugar, ou `--no-labels-file`
para que as edições valham só naquela sessão.

### Onde o clipe é salvo após revisão?

Um clipe revisado **mantém o caminho que tinha**, com a pasta do rótulo trocada
pela que você confirmou. Nada da sua posição no conjunto se perde:

```
PONTO_A/BOAALB/clipe.wav
   ├── ✔ Verdadeiro                →  verdadeiro/PONTO_A/BOAALB/clipe.wav
   ├── ✘ Falso, corrigido TURDRU   →  falso/PONTO_A/TURDRU/clipe.wav
   └── dois rótulos                →  multi/PONTO_A/BOAALB_PHYLUT/clipe.wav
```

- Os nomes dos arquivos ficam **exatamente como foram encontrados** — o rótulo
  está na pasta, então não há nada a corrigir no nome.
- Com `--label-depth`, as pastas *abaixo* do rótulo também são mantidas, no lugar
  delas: `BOAALB/PONTO_A/clipe.wav` corrigido para TURDRU vira
  `falso/TURDRU/PONTO_A/clipe.wav`.
- Um segmento com **mais de um rótulo** vai para `multi/` em vez de
  `verdadeiro/` ou `falso/`, sob uma pasta que nomeia todos os rótulos.
- Um clipe sem pasta de rótulo é arquivado direto em `verdadeiro/`, ou em
  `falso/<rótulo>/` assim que você nomear um.
- Se o nome colidir, ganha um sufixo `_2`, `_3`, … — um arquivo já revisado nunca
  é sobrescrito.
- Clipes que já estão em `verdadeiro/`, `falso/` ou `multi/` ficam fora da lista
  de pendentes, então a revisão pode ser dividida em várias sessões.

### A tabela de anotações

Com `--annotations`, cada segmento revisado é acrescentado a um CSV com as colunas
`site, file, label, start_time, end_time` — segmentos *verdadeiros* com o próprio
rótulo, *falsos* com o rótulo corrigido, e uma linha por rótulo quando o segmento
tem vários. Os tempos são a posição do clipe dentro da gravação de onde ele foi
cortado, lidos do nome e ampliados até a duração real do clipe (então o padding
entra na conta).

`file` nomeia essa gravação de origem. O nome de um clipe raramente diz de qual
gravação ele veio, então isso é procurado num `segment_sources.csv` opcional
(`segment,recording`) ao lado dos segmentos; sem ele a coluna fica vazia e a
interface avisa embaixo dos botões.

As linhas são gravadas conforme cada veredito é dado, e uma tabela existente é
complementada, então revisões em várias sessões se somam.

---

## Outras convenções de nome

Nomes que não casam continuam perfeitamente revisáveis — a interface só mostra
menos sobre eles, e não mostra nada de que não tenha certeza. Para recuperar o
ponto, o horário, a janela e o escore, diga ao `--filename-pattern` como o nome é
construído.

### Escrevendo um modelo

A forma fácil: **escreva o nome, com as partes nomeadas entre colchetes.** Tudo
fora dos colchetes é comparado literalmente.

```bash
# PONTO_A_20240115T053000_REC_12.0_17.0_BOAALB_0.873.wav
segment-reviewer ~/segmentos \
    --filename-pattern '[site]_YYYYMMDDTHHMMSS_REC_[start_time]_[end_time]_[label]_[score]'
```

| No modelo | Corresponde a |
|---|---|
| `[site]`, `[label]` | texto livre — pode conter underscores |
| `YYYYMMDD`, `HHMMSS` | a data e a hora, escritas soltas ou como `[date]`/`[time]` |
| `[datetime]` | as duas de uma vez, em qualquer formato — use com `--datetime-format` |
| `[start_time]`, `[end_time]` | a janela do clipe na gravação, em segundos |
| `[score]` | um número de similaridade ou confiança |
| `[extra]` | o que sobrar, mostrado na interface como *extra* |
| `*` | qualquer coisa, sem capturar |
| qualquer outra coisa | ela mesma, literalmente |

Todo campo é opcional, mas o modelo precisa casar com o nome **inteiro** — casar
pela metade encheria a interface com dados lidos dos pedaços errados, então isso
conta como não casar. Um erro de digitação como `[speceis]` é recusado na
inicialização, em vez de ignorado em silêncio.

### Escrevendo uma expressão

Para formatos que nenhum modelo descreve, `--filename-pattern` continua aceitando
**qualquer expressão regular com grupos nomeados** — `site`, `date`, `time`,
`datetime`, `start`, `end`, `label`, `score`, `extra`, todos opcionais, aplicados
ao nome do arquivo sem a extensão:

```bash
# rótulo primeiro, depois o ponto, depois um timestamp de 12 dígitos:
# BOAALB-pontoA-202401150530.wav
segment-reviewer ~/segmentos \
    --filename-pattern '^(?P<label>[A-Z]+)-(?P<site>\w+)-(?P<datetime>\d{12})$' \
    --datetime-format '%Y%m%d%H%M'
```

### De onde vem o rótulo

`--label-from` escolhe: `folder` (o padrão), `filename` (o grupo `label` do
padrão) ou `none`. Um padrão que captura um grupo `label` muda sozinho para
`filename`, a menos que você diga o contrário — e nesse modo o clipe é arquivado
direto, com o **nome reescrito** para carregar o rótulo confirmado.

Para manter as pastas, diga isso. Com segmentos organizados como
`[rótulo]/[ponto]_AAAAMMDD/clipe.wav`, o comando abaixo lê o rótulo da pasta de
cima, mantém a pasta do ponto embaixo dele, e ainda tira ponto, horários e escore
do nome do arquivo:

```bash
segment-reviewer ~/segmentos \
    --filename-pattern '[site]_YYYYMMDDTHHMMSS_REC_[start_time]_[end_time]_[label]_[score]' \
    --label-from folder --label-depth 1
```

### A predefinição vector-search

`--filename-pattern vector-search` lê
`PONTO_AAAAMMDD_HHMMSS_INÍCIO-FIMs_ESCORE_RÓTULO.wav`, os nomes gravados pelos
notebooks de busca vetorial bioacústica, com o **rótulo e o escore de
similaridade no nome**:

```bash
segment-reviewer ~/vector_search_segments --filename-pattern vector-search --annotations
```

Como ali o rótulo mora no nome, esse modo se comporta como o notebook: os clipes
são arquivados direto em `verdadeiro/`, `falso/<rótulo>/` e `multi/`, e o **nome
do arquivo é reescrito** com os rótulos confirmados — um segmento corrigido para
`TURDRU` é salvo como `..._0.873_TURDRU.wav`, e um com dois rótulos como
`..._0.873_BOAALB_PHYLUT.wav` — para que o nome nunca guarde o rótulo errado. O
escore aparece ao lado do rótulo na interface.

---

## Revisar segmentos por SSH

Aponte a ferramenta para uma pasta remota e tudo acontece por SFTP — listar, ler
os clipes, movê-los para as pastas de veredito, gravar a tabela de anotações. Os
clipes são cacheados localmente conforme são abertos, então voltar é instantâneo.

```bash
segment-reviewer ssh://usuario@servidor:22/dados/segmentos
segment-reviewer servidor:/dados/segmentos           # estilo scp
segment-reviewer ssh://servidor/dados/segmentos --ssh-key ~/.ssh/id_campo
```

Apelidos de host, usuários, portas e chaves do `~/.ssh/config` são respeitados, e
um agente SSH em execução é usado. Uma chave de host desconhecida é recusada, a
menos que você passe `--accept-new-host-key`.

Nada é gravado fora da pasta de segmentos e nenhum clipe é apagado — os arquivos
apenas se movem entre subpastas da pasta que você indicou.

---

## Rodando num servidor

A interface é uma página web comum, então a ferramenta pode rodar onde o áudio
está e ser usada de qualquer lugar:

```bash
segment-reviewer /dados/segmentos --host 0.0.0.0 --port 8765 --no-open
```

Ao ligar num endereço que não seja o loopback, um **token de acesso** é gerado e
embutido na URL impressa; abra essa URL uma vez e o token fica num cookie. Use
`--token meusegredo` para escolher o token, ou `--no-auth` para servir sem ele.

O token afasta um curioso das suas pastas; ele não é TLS. Numa rede não confiável,
prefira Tailscale (ligar no endereço do Tailscale, ou em `0.0.0.0` com a máquina
acessível só pela tailnet) ou um túnel SSH:

```bash
# no servidor
segment-reviewer /dados/segmentos --port 8765 --no-open
# no seu notebook
ssh -N -L 8765:127.0.0.1:8765 usuario@servidor   # depois abra http://127.0.0.1:8765
```

Um revisor por vez: a lista de pendentes e a posição atual ficam no servidor,
então dois navegadores na mesma instância conduzem a mesma sessão.

---

## Opções

```
segment-reviewer SEGMENTOS [OPÇÕES]

  SEGMENTOS                     Caminho local, ou ssh://[usuário@]host[:porta]/caminho

  -l, --lang TEXT               Idioma inicial da interface: en, pt-BR  [padrão: en]
      --labels TEXT             Os únicos rótulos oferecidos, separados por vírgulas.
                                Substitui uma lista já gravada
      --labels-file TEXT        Onde a lista fica, um rótulo por linha
                                [padrão: <SEGMENTOS>/labels.txt]
      --no-labels-file          Não lê nem grava a lista; as edições valem só na sessão
      --label-from TEXT         De onde vem o rótulo: folder, filename ou none
                                [padrão: folder]
      --label-depth INTEGER     Qual pasta carrega o rótulo, contando a partir de
                                SEGMENTOS: 1 para RÓTULO/PONTO/clipe.wav. 0 é a pasta
                                em que o clipe está  [padrão: 0]
      --filename-pattern TEXT   'default', 'vector-search', um modelo como
                                '[site]_YYYYMMDD_HHMMSS_[label]_[score]', ou uma regex
                                com os grupos nomeados site, date, time, datetime,
                                start, end, label, score, extra  [padrão: default]
      --datetime-format TEXT    Formato strptime da data e hora capturadas
                                [padrão: %Y%m%d%H%M%S]
      --no-multi-label          Limita cada segmento a um rótulo (vários rótulos é o
                                padrão; esses clipes vão para multi/)
      --annotations             Grava a tabela de anotações
      --annotations-path TEXT   Onde ela fica  [padrão: <SEGMENTOS>/annotations.csv]

      --spec-type [mel|fft|log] Eixo de frequência inicial: escala mel, Hz linear ou
                                Hz logarítmico  [padrão: mel]
      --fmin INTEGER            Frequência mínima inicial, Hz  [padrão: 0]
      --fmax INTEGER            Frequência máxima inicial, Hz; 0 = Nyquist  [padrão: 0]
      --db-floor INTEGER        Valor mínimo em dB inicial  [padrão: -80]

      --true-dir TEXT           Pasta dos segmentos aceitos  [padrão: conforme --lang]
      --false-dir TEXT          Pasta dos segmentos rejeitados  [padrão: conforme --lang]
      --multi-dir TEXT          Pasta dos segmentos com vários rótulos  [padrão: multi]

      --host TEXT               Endereço para servir  [padrão: 127.0.0.1]
  -p, --port INTEGER            Porta  [padrão: 8765]
      --token TEXT              Token de acesso da interface
      --no-auth                 Serve sem token de acesso
      --open / --no-open        Abre o navegador ao iniciar  [padrão: abre]

      --ssh-user / --ssh-port / --ssh-key / --ssh-password
      --known-hosts TEXT        known_hosts adicional a confiar
      --accept-new-host-key     Aceita uma chave de host SSH desconhecida
      --cache-dir TEXT          Onde os clipes remotos são cacheados  [padrão: pasta temporária]

      --version                 Mostra a versão e sai
```

### Nomes das pastas de veredito e idioma

Começar em inglês guarda os clipes em `true/` e `false/`; começar em português,
em `verdadeiro/` e `falso/`. **Trocar o idioma no navegador não renomeia as
pastas** — uma revisão dividida em duas sessões continua num lugar só. Use
`--true-dir` / `--false-dir` / `--multi-dir` para escolher os nomes.

Pastas gravadas em *qualquer* uma das convenções ficam sempre fora da lista de
pendentes, então uma pasta revisada em inglês não volta para revisão em português.

---

## Desenvolvimento

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
```

A suíte cobre as regras de nome, os layouts de veredito, a API HTTP e uma revisão
completa conduzida por um servidor SFTP em processo. Os helpers sem DOM do cliente
rodam no node, e se pulam sozinhos quando o node não está instalado.

Antes de dar push, vale uma rodada como a CI enxerga:

```bash
GITHUB_ACTIONS=true uv run pytest
```

O rich colore a ajuda do Typer sempre que acha que está num terminal, e no GitHub
Actions ele sempre acha — o que muda a saída renderizada o bastante para quebrar
um teste que passa localmente.

## Licença

MIT — veja [LICENSE](LICENSE).
