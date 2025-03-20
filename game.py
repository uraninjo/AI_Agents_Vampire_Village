import random
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from google.api_core.exceptions import ResourceExhausted  # Importing the error type
from colorama import Fore, Style

class Agent:
    def __init__(self, name, role):
        self.name = name
        self.role = role  # 'villager' or 'vampire'
        self.is_alive = True
        self.history = []  # Konuşma geçmişi
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
        self.add_info = ""
    
    def safe_invoke(self, chain, inputs):
        """Helper function to wait 5 seconds and retry when a quota (resource) error is encountered."""
        while True:
            try:
                response = chain.invoke(inputs)
                return response
            except ResourceExhausted:
                print(f"{self.name}: Resource exhausted, waiting 5 seconds and retrying.")
                time.sleep(5)
    
    def speak(self, phase, extra_input=""):
        """
        Generates a message according to the specified phase.
        The prompt uses the {input} placeholder.
        """
        if phase == "morning":
            if self.role == "vampire":
                alive_vampires = self.get_alive_vampires()
                prompt = ChatPromptTemplate.from_messages([
                    ("system", f"You are a vampire in a village game. The morning discussion has started. You must act naturally and avoid suspicion. Use logic to subtly shift blame or create reasonable doubt against villagers. Other vampires in the game: {', '.join(alive_vampires)}. Your name is {self.name}"),
                    ("human", "{input}")
                ])
            else:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", f"You are an agent in a village game. It's morning. Express your initial thoughts naturally. Your name is {self.name}"),
                    ("human", "{input}")
                ])

        elif phase == "defense":
            if self.role == "vampire":
                alive_vampires = self.get_alive_vampires()
                prompt = ChatPromptTemplate.from_messages([
                    ("system", f"You are a vampire in a village game. You are being accused and must defend yourself convincingly. Deny any claims against you and provide logical counterarguments. Avoid making statements that could expose your role. Other vampires in the game: {', '.join(alive_vampires)}. Your name is {self.name}"),
                    ("human", "{input}")
                ])
            else:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", f"You are an agent in a village game. It's time for your defense. Respond naturally and convincingly, defending your innocence. If anyone has accused you, address their concerns. Your name is {self.name}"),
                    ("human", "{input}")
                ])

        elif phase == "vampire":
            alive_vampires = self.get_alive_vampires()
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"You are a vampire in a village game. In your secret chat, discuss strategy and propose a candidate for elimination. Collaborate with your fellow vampires: {', '.join(alive_vampires)}. Be strategic and avoid suspicion. Your name is {self.name}"),
                ("human", "{input}")
            ])

        elif phase == "vote":
            if self.role == "vampire":
                alive_vampires = self.get_alive_vampires()
                prompt = ChatPromptTemplate.from_messages([
                    ("system", f"You are a vampire in a village game. It is time to vote for elimination. Your goal is to subtly manipulate the vote to protect fellow vampires ({', '.join(alive_vampires)}) and eliminate strategic threats. Do NOT make obviously biased votes. Instead, base your reasoning on observed behavior, inconsistencies, or logical arguments that align with the village’s suspicions. Try to influence the group’s vote without drawing attention to yourself. Use the format: 'CandidateName: Explanation'. Your name is {self.name}"),
                    ("human", "{input}")
                ])
            else:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", f"You are an agent in a village game. It is time to vote for elimination. Analyze the behavior and statements of your fellow agents. You must NOT vote for yourself. Cast your vote by providing both the candidate's name and a clear, specific explanation based on observed behaviors or statements. Your name is {self.name}"),
                    ("human", "{input}")
                ])

        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"Express your thoughts. Your name is {self.name}"),
                ("human", "{input}")
            ])
        global_history_snippet = "\n".join(self.game.global_history) if self.game.global_history else ""

        if phase == "vampire":
            vampire_history_snippet = "\n".join(self.game.vampire_history) if self.game.vampire_history else ""
            full_input = f"Content of what vampires have spoken: {vampire_history_snippet}\nContent of what villagers have spoken: {global_history_snippet}\n{extra_input}"
        else:
            full_input = f"{global_history_snippet}\n{extra_input}"

        chain = prompt | self.llm
        response = self.safe_invoke(chain, {"input": full_input})
        
        if phase != "vampire":
            self.game.global_history.append(f"{self.name} ({phase}): {response.content}")
        else:
            self.game.vampire_history.append(f"{self.name} ({phase}): {response.content}")
        self.history.append(f"{self.name} ({phase}): {response.content}")
        return response.content
    
    def select_candidate(self, candidates):
        """
        For vampires: Determines the name of the candidate suspected among the living villagers.
        """
        candidate_list_str = ", ".join(candidates)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a vampire in a village game. From the following list of candidates, choose the one you suspect most to be a true villager. Provide only the candidate's name."),
            ("human", "Candidates: {candidates}")
        ])
        chain = prompt | self.llm
        response = self.safe_invoke(chain, {"candidates": candidate_list_str})
        candidate = response
        return candidate
    
    def revise_candidate(self, other_candidate, candidates):
        """
        For vampires: If the vampires' initial candidate selections differ, revise the candidate to reach a consensus.
        """
        candidate_list_str = ", ".join(candidates)
        prompt_text = (
            f"Your colleague suggested eliminating '{other_candidate}', but you might have a different opinion. "
            f"Given the candidates: {candidate_list_str}, propose a revised candidate that both of you could agree upon. Provide only the candidate's name."
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Discuss with your fellow vampire and propose a common target."),
            ("human", "{input}")
        ])
        chain = prompt | self.llm
        response = self.safe_invoke(chain, {"input": prompt_text})
        candidate = response
        return candidate

class Game:
    def __init__(self, vampire_count=2, villager_count=6):
        self.agents = []
        self.round = 0
        self.vampire_count = vampire_count
        self.villager_count = villager_count
        self.global_history = []  # 🔹 Tüm ajanların konuşmalarını saklamak için ortak geçmiş
        self.vampire_history = []
        self.setup_agents()
    
    def setup_agents(self):
        """
        Creates 8 agents: 6 villagers, 2 vampires.
        Roles are assigned randomly.
        """
        roles = ['villager'] * self.villager_count + ['vampire'] * self.vampire_count
        random.shuffle(roles)
        for i, role in enumerate(roles, start=1):
            agent = Agent(name=f"Agent {i}", role=role)  # Önce nesneyi oluştur
            agent.game = self  # 🔹 Ajanların `Game` nesnesine erişebilmesi için referans veriyoruz
            self.agents.append(agent)
        # Assigning colors: Different shades of red for vampires, and various colors for villagers
        vampire_colors = [Fore.LIGHTRED_EX, Fore.RED, Fore.MAGENTA]
        villager_colors = [Fore.CYAN, Fore.GREEN, Fore.BLUE, Fore.LIGHTBLUE_EX, Fore.YELLOW, Fore.LIGHTGREEN_EX]
        
        v_index = 0
        vi_index = 0
        for agent in self.agents:
            if agent.role == 'vampire':
                agent.speech_color = vampire_colors[v_index % len(vampire_colors)]
                v_index += 1
            else:
                agent.speech_color = villager_colors[vi_index % len(villager_colors)]
                vi_index += 1

        print("Players created:")
        for agent in self.agents:
            role_name = "Vampire" if agent.role == 'vampire' else "Villager"
            print(f"{agent.speech_color}{agent.name}: {role_name}{Style.RESET_ALL}\n")
    
    def get_alive_agents(self):
        return [agent for agent in self.agents if agent.is_alive]
    
    def get_alive_villagers(self):
        return [agent for agent in self.agents if agent.is_alive and agent.role == 'villager']
    
    def get_alive_vampires(self):
        return [agent for agent in self.agents if agent.is_alive and agent.role == 'vampire']
    
    def morning_chat(self):
        """
        Morning chat: All living agents freely produce their morning messages.
        """
        print("\n--- Morning Chat ---")
        for agent in self.get_alive_agents():
            message = agent.speak("morning", extra_input="Share your thoughts for the morning.")
            print(f"{agent.speech_color}{agent.name}: {message}{Style.RESET_ALL}\n")
            time.sleep(1)
    
    def defense_phase(self):
        """
        Defense phase: Living agents present their defenses in a random order.
        """
        print("\n--- Defense Phase ---")
        alive_agents = self.get_alive_agents()
        random.shuffle(alive_agents)
        for agent in alive_agents:
            message = agent.speak("defense", extra_input="Defend yourself.")
            print(f"{agent.speech_color}{agent.name} (Defense): {message}{Style.RESET_ALL}\n")
            time.sleep(1)

    def voting_phase(self):
        """
        Voting phase: All living agents vote on who should be eliminated.
        Each agent must vote by providing both the candidate's name and a concrete explanation for their choice.
        Voting for oneself is not allowed.
        If a valid response is not received, a maximum of 3 attempts is allowed.
        The candidate with the most votes is eliminated.
        """
        print("\n--- Voting Phase ---")
        candidates = [agent.name for agent in self.get_alive_agents()]
        votes = {}
        
        for agent in self.get_alive_agents():
            valid_vote = False
            attempt = 0
            vote_response_text = ""
            while not valid_vote and attempt < 3:
                attempt += 1
                vote_response_text = agent.speak("vote", extra_input="Candidates: " + ", ".join(candidates))
                vote_response_text = vote_response_text.strip()
                parts = vote_response_text.split(":", 1)
                if len(parts) == 2:
                    candidate_vote = parts[0].strip()
                    explanation = parts[1].strip()
                    # Valid response check: candidate must be in the list, not the voter themselves,
                    # explanation must not be empty, have at least 4 words, and not contain unwanted phrases.
                    if (candidate_vote in candidates and candidate_vote != agent.name and explanation and 
                        len(explanation.split()) >= 4 and
                        ("My reasoning" not in explanation and "Your reasoning" not in explanation)):
                        valid_vote = True
                        break
                # If an invalid response is received, remind the agent.
                print(f"{agent.speech_color}{agent.name} (Voting): Your response is not in a valid format. Please vote in the format 'CandidateName: Explanation' without extra phrases and without voting for yourself.{Style.RESET_ALL}\n")
                time.sleep(1)
            if not valid_vote:
                # After maximum attempts, if a valid response is not obtained, choose randomly from valid candidates (excluding self).
                valid_candidates = [c for c in candidates if c != agent.name]
                candidate_vote = random.choice(valid_candidates) if valid_candidates else agent.name
                explanation = "Invalid vote response."
            print(f"{agent.speech_color}{agent.name} (Voting): {candidate_vote} - {explanation}{Style.RESET_ALL}\n")
            votes[candidate_vote] = votes.get(candidate_vote, 0) + 1
            time.sleep(1)
        
        max_votes = max(votes.values())
        potential_targets = [name for name, count in votes.items() if count == max_votes]
        chosen_candidate = random.choice(potential_targets)
        print(f"\nAs a result of the vote, the candidate with the most votes: {chosen_candidate} is eliminated.\n")
        target_agent = next((agent for agent in self.get_alive_agents() if agent.name == chosen_candidate), None)
        if target_agent:
            target_agent.is_alive = False

    def night_phase(self):
        """
        Night phase: Only vampires speak in the secret channel, and they cannot choose a target without consensus.
        Vampires first choose their individual candidates, then discuss to reach a consensus.
        """
        print("\n--- Night Phase (Vampires' Turn) ---")
        vampires = self.get_alive_vampires()
        if not vampires:
            print("No vampires remaining. Night phase is skipped.")
            return
        
        print("Vampires are discussing in the secret channel...\n")
        for vampire in vampires:
            message = vampire.speak("vampire", extra_input="Discuss your suspicions. Propose a candidate for elimination. Who would be perfect for raising suspicion on others?")
            print(f"{vampire.speech_color}{vampire.name} (Secret): {message}{Style.RESET_ALL}\n")
            time.sleep(1)

        villagers = self.get_alive_villagers()
        if not villagers:
            print("No villagers remain alive!")
            return
        
        candidate_names = [villager.name for villager in villagers]
        initial_choices = {}
        for vampire in vampires:
            choice = vampire.select_candidate(candidate_names)
            initial_choices[vampire.name] = choice.content
            print(f"{vampire.name}'s first choice: {choice.content}")
        
        if len(set(initial_choices.values())) == 1:
            chosen_candidate = list(initial_choices.values())[0]
            print(f"\nVampires unanimously chose {chosen_candidate} as the target.")
        else:
            print("\nVampires did not reach consensus in the first round, reaching consensus now...")
            consensus_round = 0
            max_rounds = 3
            consensus_choices = initial_choices.copy()
            while len(set(consensus_choices.values())) > 1 and consensus_round < max_rounds:
                consensus_round += 1
                new_choices = {}
                for vampire in vampires:
                    other_choices = [consensus_choices[other.name] for other in vampires if other.name != vampire.name]
                    other_choice = other_choices[0] if other_choices else consensus_choices[vampire.name]
                    revised = vampire.revise_candidate(other_choice, candidate_names)
                    new_choices[vampire.name] = revised
                    print(f"{vampire.name} revised choice: {revised}")
                    time.sleep(1)
                consensus_choices = new_choices
            if len(set(consensus_choices.values())) == 1:
                chosen_candidate = list(consensus_choices.values())[0]
                print(f"\nConsensus reached: {chosen_candidate} is chosen as the target.")
            else:
                votes = {}
                for choice in consensus_choices.values():
                    votes[choice] = votes.get(choice, 0) + 1
                max_votes = max(votes.values())
                potential_targets = [name for name, count in votes.items() if count == max_votes]
                chosen_candidate = random.choice(potential_targets)
                print(f"\nConsensus not reached. {chosen_candidate} is randomly selected as the target.")
        
        target_agent = next((agent for agent in villagers if agent.name == chosen_candidate), None)
        if target_agent:
            target_agent.is_alive = False
            print(f"\nVampires have marked {target_agent.name} as eliminated from the game!")
    
    def show_status(self):
        """
        Displays the status of each agent in the game (alive or eliminated).
        """
        print("\n--- Game Status ---")
        for agent in self.agents:
            status = "Alive" if agent.is_alive else "Eliminated"
            role_name = "Vampire" if agent.role == 'vampire' else "Villager"
            print(f"{agent.speech_color}{agent.name} ({role_name}): {status}{Style.RESET_ALL}\n")
    
    def check_win_conditions(self):
        """
        Checks the win conditions:
          - If all vampires are eliminated: Villagers win.
          - If the number of vampires is equal to or greater than the number of villagers: Vampires win.
        """
        vampires_alive = len(self.get_alive_vampires())
        villagers_alive = len(self.get_alive_villagers())
        if vampires_alive == 0:
            print("\nVillagers win! All vampires are eliminated.")
            return True
        if vampires_alive > villagers_alive:
            print("\nVampires win! They are in control.")
            return True
        return False
    
    def run_game(self):
        """
        Game loop: Each round includes morning chat, defense, voting, and night phases.
        """
        print("\nVampire Villager Game Started!")
        while True:
            self.round += 1
            print(f"\n===== ROUND {self.round} =====")
            self.morning_chat()
            self.defense_phase()
            self.voting_phase()
            self.night_phase()
            self.show_status()
            if self.check_win_conditions():
                break
            time.sleep(2)
        print("\nGame Over!")

if __name__ == "__main__":
    game = Game(vampire_count=2, villager_count=4)
    game.run_game()
