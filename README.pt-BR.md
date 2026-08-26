# Revisor de Segmentos

[← English](README.md)

Uma ferramenta de linha de comando que serve uma **interface no navegador para
revisar uma pasta de segmentos de áudio**. Cada clipe aparece como espectrograma,
com o que sua pasta e seu nome de arquivo disserem sobre ele; você escuta e marca
como **Verdadeiro** (correto) ou **Falso** (errado, com o rótulo correto). Os
clipes revisados são movidos para `verdadeiro/`, `falso/` ou `multi/` dentro da
pasta de segmentos e, opcionalmente, registrados numa tabela de anotações.

Funciona com qualquer conjunto de clipes, não importa como tenham sido gerados —
a saída de um detector, exemplos recortados à mão, as previsões de um
classificador a validar. A pasta de segmentos pode ser **local** ou **remota via
SSH**, e a interface pode ser servida para **outra máquina** na sua rede local ou
Tailscale. A interface está disponível em **Português (Brasil)** e **Inglês**,
com troca durante o uso.

> Ela também encaixa direto no fluxo dos
> [notebooks de busca vetorial bioacústica](https://github.com/biodiversica/bioacoustic-ipynbs),
> como substituta independente da etapa *Revisar segmentos extraídos* — veja
> [Outras convenções de nome](#outras-convenções-de-nome).

---

## Como um segmento é lido

Duas fontes independentes, ambas configuráveis:

**A pasta dá o rótulo.** Um conjunto revisado costuma ser organizado com uma
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

**O nome do arquivo dá o resto.** Por padrão ele é lido como

```
[ponto]_[AAAAMMDD]_[HHMMSS]_[início]_[fim]_*
      PONTO_A_20240115_053000_12.0_17.0_det1.wav
```

- O ponto pode conter underscores — a leitura se ancora na data e na hora.
- `início`/`fim` são a posição do clipe, em segundos, dentro da gravação de onde
  ele foi cortado. Os dois separadores funcionam: `12.0_17.0` e `12.0-17.0s`.
- `_*` é qualquer outra coisa, mostrada na interface como *extra*.
- Tudo depois do ponto é opcional, e **um nome que não casa com nada continua
  perfeitamente revisável** — a interface apenas mostra menos sobre ele.

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

# Rótulos extras na lista suspensa e tabela de anotações
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
| **✔ Verdadeiro** | O rótulo está certo. O clipe mantém seu caminho, sob `verdadeiro/`. |
| **✘ Falso** | Errado. Escolha ou digite o rótulo correto e clique em **Confirmar** — o clipe é arquivado sob esse rótulo. |
| **← Anterior / Próximo →** | Navega sem decidir nada. |
| **Tipo / Hz mín / Hz máx / dB** | Redesenha o espectrograma na hora. O player de áudio não é afetado, então o clipe continua tocando enquanto você muda a visualização. |
| **Rótulos** (com `--multi-label`) | Dá vários rótulos a um segmento — duas espécies cantando ao mesmo tempo. Vem preenchido com o rótulo atual do segmento; a lista suspensa acrescenta em vez de substituir. |
| **⟳** | Relê a pasta, por exemplo quando chegam mais segmentos. |
| **Idioma** | Alterna a interface entre Português e Inglês. |

A lista suspensa oferece todos os rótulos já em uso no conjunto, mais o que você
passar em `--labels`. Ela só preenche a caixa de texto — você sempre pode digitar
um rótulo que não está na lista.

Teclado: <kbd>←</kbd> <kbd>→</kbd> para navegar, <kbd>T</kbd> / <kbd>F</kbd> para
verdadeiro/falso, <kbd>Espaço</kbd> para tocar ou pausar, <kbd>Enter</kbd> para
confirmar o rótulo digitado, <kbd>Esc</kbd> para cancelar.

### Para onde um veredito leva o clipe

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

`--filename-pattern` aceita uma predefinição ou **qualquer expressão regular com
grupos nomeados**. Grupos reconhecidos: `site`, `date`, `time`, `datetime`,
`start`, `end`, `label`, `score`, `extra` — todos opcionais, aplicados ao nome do
arquivo sem a extensão.

```bash
# rótulo primeiro, depois o ponto, depois um timestamp de 12 dígitos:
# BOAALB-pontoA-202401150530.wav
segment-reviewer ~/segmentos \
    --filename-pattern '^(?P<label>[A-Z]+)-(?P<site>\w+)-(?P<datetime>\d{12})$' \
    --datetime-format '%Y%m%d%H%M'
```

`--label-from` escolhe de onde vem o rótulo: `folder` (o padrão), `filename` (o
grupo `label` do padrão) ou `none`. Um padrão que captura um grupo `label` muda
sozinho para `filename`, a menos que você diga o contrário.

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
      --labels TEXT             Rótulos extras na lista suspensa, separados por vírgulas.
                                Os rótulos já em uso no conjunto são sempre oferecidos
      --label-from TEXT         De onde vem o rótulo: folder, filename ou none
                                [padrão: folder]
      --filename-pattern TEXT   'default', 'vector-search', ou uma regex com os grupos
                                nomeados site, date, time, datetime, start, end, label,
                                score, extra  [padrão: default]
      --datetime-format TEXT    Formato strptime da data e hora capturadas
                                [padrão: %Y%m%d%H%M%S]
      --multi-label             Permite vários rótulos por segmento (arquivos em multi/)
      --annotations             Grava a tabela de anotações
      --annotations-path TEXT   Onde ela fica  [padrão: <SEGMENTOS>/annotations.csv]

      --spec-type [mel|fft]     Tipo inicial do espectrograma  [padrão: mel]
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
completa conduzida por um servidor SFTP em processo.

## Licença

MIT — veja [LICENSE](LICENSE).
